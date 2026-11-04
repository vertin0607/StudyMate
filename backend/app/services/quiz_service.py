"""生成检测、评分，并在评分成功后更新掌握度。"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan, StudyTask
from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
from app.services import goal_service
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_repair_messages
from app.services.ai.quiz_parser import (
    SUBJECTIVE,
    GradeDraft,
    QuizDraft,
    answers_match,
    normalize_answer,
    parse_grades,
    parse_quiz,
)
from app.services.mastery import next_mastery, result_label, status_label

logger = logging.getLogger(__name__)
QUIZ_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "quiz.txt"
GRADE_PROMPT = QUIZ_PROMPT.with_name("grade.txt")


def generate_for_task(session: Session, task_id: int) -> dict:
    task, plan, goal = _task_context(session, task_id)
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="完成这项学习后才能开始知识检测")
    existing = session.exec(
        select(Quiz)
        .where(Quiz.task_id == task.id, Quiz.status == "ready")
        .order_by(Quiz.created_at.desc())
    ).first()
    if existing is not None:
        return _public_quiz(session, existing)

    points = list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id)).all())
    allowed = {point.id for point in points if point.id is not None}
    if not allowed:
        raise HTTPException(status_code=400, detail="当前目标还没有知识点，无法出题")
    focus_id = task.knowledge_point_id if task.knowledge_point_id in allowed else None
    draft = _request_quiz(goal, plan, task, points, allowed, focus_id)
    now = datetime.now(timezone.utc)
    quiz = Quiz(
        goal_id=goal.id,
        plan_id=plan.id,
        task_id=task.id,
        title=draft.title,
        status="ready",
        created_at=now,
    )
    session.add(quiz)
    session.flush()
    for index, item in enumerate(draft.questions):
        session.add(
            QuizQuestion(
                quiz_id=quiz.id,
                knowledge_point_id=item.knowledge_point_id,
                sort_order=index,
                question_type=item.question_type,
                difficulty=item.difficulty,
                stem=item.stem,
                options_json=json.dumps(item.options, ensure_ascii=False),
                correct_answer=item.correct_answer,
                explanation=item.explanation,
                created_at=now,
            )
        )
    goal_service.commit_or_raise(session)
    session.refresh(quiz)
    logger.info("已保存知识检测 %s", quiz.id)
    return _public_quiz(session, quiz)


def get_quiz(session: Session, quiz_id: int) -> dict:
    quiz = _get_quiz(session, quiz_id)
    if quiz.status == "completed":
        return get_result(session, quiz_id)
    return _public_quiz(session, quiz)


def get_result(session: Session, quiz_id: int) -> dict:
    quiz = _get_quiz(session, quiz_id)
    if quiz.status != "completed":
        raise HTTPException(status_code=409, detail="检测还没有提交，暂时没有结果")
    return _result_payload(session, quiz)


def submit_quiz(session: Session, quiz_id: int, answers: list[dict]) -> dict:
    quiz = _get_quiz(session, quiz_id)
    if quiz.status == "completed":
        raise HTTPException(status_code=409, detail="这份检测已经提交，不能重复评分")
    if quiz.status != "ready":
        raise HTTPException(status_code=409, detail="这份检测当前不能提交")
    questions = _questions(session, quiz.id)
    incoming = {int(item["question_id"]): str(item.get("answer", "")) for item in answers}
    expected = {question.id for question in questions if question.id is not None}
    if set(incoming) != expected:
        raise HTTPException(status_code=422, detail="需要为每一道题提交答案")

    subjective = [question for question in questions if question.question_type in SUBJECTIVE]
    grades: dict[int, GradeDraft] = {}
    if subjective:
        grades = {item.question_id: item for item in _request_grades(subjective, incoming)}

    now = datetime.now(timezone.utc)
    point_scores: dict[int, list[int]] = {}
    errors: dict[int, list[str]] = {}
    correct_count = 0
    for question in questions:
        assert question.id is not None
        if question.question_type in SUBJECTIVE:
            grade = grades[question.id]
            score = grade.score
            correct = grade.correct
            error_reason = grade.error_reason
            suggestion = grade.suggestion
        else:
            correct = answers_match(question.question_type, question.correct_answer, incoming[question.id])
            score = 100 if correct else 0
            error_reason = "" if correct else "选项与正确答案不一致"
            suggestion = "可以对照解析再看一遍这个知识点" if not correct else "这道题的关键点已经对上"
        answer_text = normalize_answer(question.question_type, incoming[question.id])
        session.add(
            QuizAnswer(
                question_id=question.id,
                user_answer=answer_text,
                is_correct=correct,
                score=score,
                error_reason=error_reason,
                suggestion=suggestion,
                created_at=now,
            )
        )
        question.score = score
        session.add(question)
        point_scores.setdefault(question.knowledge_point_id, []).append(score)
        if not correct and error_reason:
            errors.setdefault(question.knowledge_point_id, []).append(error_reason)
        correct_count += int(correct)

    total = round(sum(question.score or 0 for question in questions) / len(questions))
    point_results = _apply_mastery(session, quiz, point_scores, now)
    from app.services.review_service import apply_after_quiz

    apply_after_quiz(session, quiz, point_scores, errors, now)
    names = {point.id: point.name for point in session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == quiz.goal_id)).all()}
    quiz.status = "completed"
    quiz.score = total
    quiz.correct_count = correct_count
    quiz.wrong_count = len(questions) - correct_count
    quiz.suggestion = _suggestion([(names.get(point_id, "知识点"), score) for point_id, score in point_results])
    quiz.submitted_at = now
    session.add(quiz)
    goal_service.commit_or_raise(session)
    session.refresh(quiz)
    return _result_payload(session, quiz)


def history(session: Session, goal_id: int) -> dict:
    goal_service.get_goal(session, goal_id)
    quizzes = session.exec(
        select(Quiz).where(Quiz.goal_id == goal_id, Quiz.status == "completed").order_by(Quiz.submitted_at.desc())
    ).all()
    return {
        "quizzes": [
            {
                "id": quiz.id,
                "title": quiz.title,
                "score": quiz.score,
                "correct_count": quiz.correct_count,
                "wrong_count": quiz.wrong_count,
                "level_label": result_label(quiz.score or 0),
                "submitted_at": quiz.submitted_at,
            }
            for quiz in quizzes
        ]
    }


def list_knowledge(session: Session, goal_id: int | None) -> dict:
    goals = goal_service.list_goals(session)
    if goal_id is not None:
        goal_service.get_goal(session, goal_id)
        goals = [goal for goal in goals if goal.id == goal_id]
    goal_ids = [goal.id for goal in goals if goal.id is not None]
    points = []
    if goal_ids:
        points = list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids)).order_by(KnowledgePoint.id)).all())
    return {"points": [_point_payload(session, point) for point in points]}


def get_knowledge(session: Session, knowledge_id: int) -> dict:
    point = _get_point(session, knowledge_id)
    return _point_payload(session, point)


def knowledge_history(session: Session, knowledge_id: int) -> dict:
    point = _get_point(session, knowledge_id)
    events = session.exec(
        select(KnowledgeMasteryEvent)
        .where(KnowledgeMasteryEvent.knowledge_point_id == point.id)
        .order_by(KnowledgeMasteryEvent.created_at.desc())
    ).all()
    return {
        "knowledge_point_id": point.id,
        "name": point.name,
        "events": [
            {
                "id": event.id,
                "previous_level": event.previous_level,
                "new_level": event.new_level,
                "quiz_score": event.quiz_score,
                "reason": event.reason,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


def analytics(session: Session) -> dict:
    goals = goal_service.list_goals(session)
    goal_ids = [goal.id for goal in goals if goal.id is not None]
    payload = {
        "completed_tasks": 0,
        "quiz_count": 0,
        "average_score": None,
        "mastered_count": 0,
        "needs_review_count": 0,
        "latest_score": None,
        "points": [],
    }
    if not goal_ids:
        return payload
    tasks = session.exec(
        select(StudyTask)
        .join(StudyPlan, StudyPlan.id == StudyTask.plan_id)
        .where(StudyPlan.goal_id.in_(goal_ids), StudyTask.status == "completed")
    ).all()
    quizzes = session.exec(
        select(Quiz).where(Quiz.goal_id.in_(goal_ids), Quiz.status == "completed").order_by(Quiz.submitted_at.desc())
    ).all()
    points = list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids)).order_by(KnowledgePoint.id)).all())
    scores = [quiz.score for quiz in quizzes if quiz.score is not None]
    payload.update(
        {
            "completed_tasks": len(tasks),
            "quiz_count": len(quizzes),
            "average_score": round(sum(scores) / len(scores)) if scores else None,
            "mastered_count": sum(1 for point in points if point.status in {"basic", "proficient", "mastered"}),
            "needs_review_count": sum(1 for point in points if point.status == "needs_review"),
            "latest_score": scores[0] if scores else None,
            "points": [_point_payload(session, point) for point in points],
        }
    )
    return payload


def recent_quiz_results(session: Session, goal_id: int) -> list[dict]:
    quizzes = session.exec(
        select(Quiz).where(Quiz.goal_id == goal_id, Quiz.status == "completed").order_by(Quiz.submitted_at.desc()).limit(5)
    ).all()
    results = []
    for quiz in quizzes:
        results.append(
            {
                "quiz_id": quiz.id,
                "title": quiz.title,
                "score": quiz.score,
                "level_label": result_label(quiz.score or 0),
                "suggestion": quiz.suggestion,
            }
        )
    return results


def _request_quiz(goal, plan, task, points, allowed: set[int], focus_id: int | None) -> QuizDraft:
    payload = {
        "goal": {"title": goal.title, "description": goal.description},
        "plan": {"title": plan.title, "description": plan.description},
        "task": {"title": task.title, "description": task.description},
        "focus_knowledge_point_id": focus_id,
        "knowledge_points": [
            {
                "id": point.id,
                "name": point.name,
                "status": point.status,
                "mastery_level": point.mastery_level,
                "mastery_assessed": point.mastery_level > 0 or point.status == "mastered",
            }
            for point in points
        ],
    }
    messages = [
        {"role": "system", "content": QUIZ_PROMPT.read_text(encoding="utf-8")},
        {"role": "user", "content": "请根据这次学习出题：\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    last_error = "检测题目未通过校验"
    raw = ""
    for attempt in range(MAX_ATTEMPTS):
        raw = complete_json(messages)
        try:
            return parse_quiz(raw, allowed, focus_id)
        except AIError as exc:
            last_error = exc.message
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            messages = build_repair_messages(messages, raw, exc.message)
    raise AIError(last_error, status_code=502)


def _request_grades(questions: list[QuizQuestion], answers: dict[int, str]) -> list[GradeDraft]:
    expected = {question.id for question in questions if question.id is not None}
    payload = {
        "questions": [
            {
                "question_id": question.id,
                "stem": question.stem,
                "reference_answer": question.correct_answer,
                "user_answer": answers.get(question.id or 0, ""),
            }
            for question in questions
        ]
    }
    messages = [
        {"role": "system", "content": GRADE_PROMPT.read_text(encoding="utf-8")},
        {"role": "user", "content": "请为下面的回答评分：\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    last_error = "简答评分未通过校验"
    raw = ""
    for attempt in range(MAX_ATTEMPTS):
        raw = complete_json(messages)
        try:
            return parse_grades(raw, expected)
        except AIError as exc:
            last_error = exc.message
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            messages = build_repair_messages(messages, raw, exc.message)
    raise AIError(last_error, status_code=502)


def _apply_mastery(session: Session, quiz: Quiz, point_scores: dict[int, list[int]], now: datetime) -> list[tuple[int, int]]:
    results: list[tuple[int, int]] = []
    for point_id, scores in point_scores.items():
        point = session.get(KnowledgePoint, point_id)
        if point is None:
            continue
        latest = round(sum(scores) / len(scores))
        events = session.exec(
            select(KnowledgeMasteryEvent)
            .where(KnowledgeMasteryEvent.knowledge_point_id == point.id)
            .order_by(KnowledgeMasteryEvent.created_at)
        ).all()
        previous = None if not events else point.mastery_level
        history = [event.quiz_score for event in events]
        level, status, reason = next_mastery(previous, history, latest)
        session.add(
            KnowledgeMasteryEvent(
                knowledge_point_id=point.id,
                quiz_id=quiz.id,
                previous_level=previous,
                new_level=level,
                quiz_score=latest,
                reason=reason[:500],
                created_at=now,
            )
        )
        point.mastery_level = level
        point.status = status
        point.updated_at = now
        session.add(point)
        results.append((point_id, latest))
    return results


def _suggestion(items: list[tuple[str, int]]) -> str:
    weak = [name for name, score in items if score < 60]
    review = [name for name, score in items if 60 <= score < 90]
    strong = [name for name, score in items if score >= 90]
    parts: list[str] = []
    if weak:
        parts.append("下一步先复习" + "、".join(weak))
    if review:
        parts.append("可以再用一个新例子巩固" + "、".join(review))
    if strong:
        parts.append("、".join(strong) + "这次表现较好，但一次高分还不会直接记成熟练掌握")
    return "。".join(parts) or "可以先看解析，再决定要不要重做相关内容。"


def _task_context(session: Session, task_id: int):
    task = session.get(StudyTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="学习任务不存在")
    plan = session.get(StudyPlan, task.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="学习任务不存在")
    goal = goal_service.get_goal(session, plan.goal_id)
    if plan.status != "active":
        raise HTTPException(status_code=409, detail="只能检测当前计划中的任务")
    return task, plan, goal


def _get_quiz(session: Session, quiz_id: int) -> Quiz:
    quiz = session.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="知识检测不存在")
    goal_service.get_goal(session, quiz.goal_id)
    return quiz


def _get_point(session: Session, knowledge_id: int) -> KnowledgePoint:
    point = session.get(KnowledgePoint, knowledge_id)
    if point is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    goal_service.get_goal(session, point.goal_id)
    return point


def _questions(session: Session, quiz_id: int | None) -> list[QuizQuestion]:
    if quiz_id is None:
        return []
    return list(session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.sort_order)).all())


def _public_quiz(session: Session, quiz: Quiz) -> dict:
    questions = []
    for question in _questions(session, quiz.id):
        point = session.get(KnowledgePoint, question.knowledge_point_id)
        questions.append(
            {
                "id": question.id,
                "sort_order": question.sort_order,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "stem": question.stem,
                "options": json.loads(question.options_json),
                "knowledge_point_name": None if point is None else point.name,
            }
        )
    return {
        "id": quiz.id,
        "goal_id": quiz.goal_id,
        "task_id": quiz.task_id,
        "title": quiz.title,
        "status": quiz.status,
        "question_count": len(questions),
        "questions": questions,
    }


def _result_payload(session: Session, quiz: Quiz) -> dict:
    questions = []
    updates = []
    seen_points: set[int] = set()
    for question in _questions(session, quiz.id):
        answer = session.exec(select(QuizAnswer).where(QuizAnswer.question_id == question.id)).first()
        point = session.get(KnowledgePoint, question.knowledge_point_id)
        questions.append(
            {
                "id": question.id,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "stem": question.stem,
                "options": json.loads(question.options_json),
                "knowledge_point_name": None if point is None else point.name,
                "user_answer": "" if answer is None else answer.user_answer,
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
                "is_correct": False if answer is None else answer.is_correct,
                "score": 0 if answer is None else answer.score,
                "error_reason": "" if answer is None else answer.error_reason,
                "suggestion": "" if answer is None else answer.suggestion,
            }
        )
        if point is not None and point.id not in seen_points:
            seen_points.add(point.id)
            event = session.exec(
                select(KnowledgeMasteryEvent)
                .where(KnowledgeMasteryEvent.knowledge_point_id == point.id, KnowledgeMasteryEvent.quiz_id == quiz.id)
                .order_by(KnowledgeMasteryEvent.created_at.desc())
            ).first()
            if event is not None:
                updates.append(
                    {
                        "knowledge_point_id": point.id,
                        "name": point.name,
                        "previous_level": event.previous_level,
                        "new_level": event.new_level,
                        "quiz_score": event.quiz_score,
                        "status": point.status,
                        "status_label": status_label(point.status, True),
                        "reason": event.reason,
                    }
                )
    return {
        "id": quiz.id,
        "goal_id": quiz.goal_id,
        "title": quiz.title,
        "status": quiz.status,
        "score": quiz.score,
        "correct_count": quiz.correct_count,
        "wrong_count": quiz.wrong_count,
        "level_label": result_label(quiz.score or 0),
        "suggestion": quiz.suggestion,
        "submitted_at": quiz.submitted_at,
        "questions": questions,
        "mastery_updates": updates,
        "reviews": _review_summaries(session, quiz),
    }


def _review_summaries(session: Session, quiz: Quiz) -> list[dict]:
    from app.services.review_service import summaries_for_quiz

    return summaries_for_quiz(session, quiz)


def _point_payload(session: Session, point: KnowledgePoint) -> dict:
    event = session.exec(
        select(KnowledgeMasteryEvent)
        .where(KnowledgeMasteryEvent.knowledge_point_id == point.id)
        .order_by(KnowledgeMasteryEvent.created_at.desc())
    ).first()
    assessed = event is not None or point.status == "mastered"
    return {
        "id": point.id,
        "goal_id": point.goal_id,
        "name": point.name,
        "status": point.status,
        "status_label": status_label(point.status, assessed),
        "mastery_level": None if not assessed else point.mastery_level,
        "mastery_assessed": assessed,
        "recent_quiz_score": None if event is None else event.quiz_score,
        "memory": _memory(session, point),
    }


def _memory(session: Session, point: KnowledgePoint) -> dict:
    from app.services.review_service import memory_profile

    return memory_profile(session, point)
