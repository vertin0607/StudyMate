import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./layouts/AppLayout.tsx";
import { DashboardPage } from "./pages/DashboardPage.tsx";
import { GoalDetailPage } from "./pages/GoalDetailPage.tsx";
import { GoalsPage } from "./pages/GoalsPage.tsx";
import { PlaceholderPage } from "./pages/PlaceholderPage.tsx";
import { PlansPage } from "./pages/PlansPage.tsx";
import { ProblemDetailPage } from "./pages/ProblemDetailPage.tsx";
import { ProblemImportPage } from "./pages/ProblemImportPage.tsx";
import { ProblemsPage } from "./pages/ProblemsPage.tsx";
import { ProblemTopicsPage } from "./pages/ProblemTopicsPage.tsx";
import { WrongProblemsPage } from "./pages/WrongProblemsPage.tsx";
import { ProgressPage } from "./pages/ProgressPage.tsx";
import { QuizPage } from "./pages/QuizPage.tsx";
import { ReviewDetailPage } from "./pages/ReviewDetailPage.tsx";
import { ReviewsPage } from "./pages/ReviewsPage.tsx";
import { TutorPage } from "./pages/TutorPage.tsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/goals" element={<GoalsPage />} />
        <Route path="/goals/:id" element={<GoalDetailPage />} />
        <Route path="/plans" element={<PlansPage />} />
        <Route path="/tutor" element={<TutorPage />} />
        <Route path="/tutor/:sessionId" element={<TutorPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/reviews/:scheduleId" element={<ReviewDetailPage />} />
        <Route
          path="/learning/:lessonId"
          element={
            <PlaceholderPage
              title="AI 学习课堂"
              phase="后续阶段"
              summary="这里将按当天任务讲解知识点，并保留课程内容。"
            />
          }
        />
        <Route path="/quiz/:quizId" element={<QuizPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/problems" element={<ProblemsPage />} />
        <Route path="/problems/import" element={<ProblemImportPage />} />
        <Route path="/problems/topics" element={<ProblemTopicsPage />} />
        <Route path="/problems/wrong" element={<WrongProblemsPage />} />
        <Route path="/problems/:problemId" element={<ProblemDetailPage />} />
        <Route
          path="/reports"
          element={
            <PlaceholderPage
              title="学习汇报"
              phase="后续阶段"
              summary="每天学习结束后在这里提交汇报。长期计划的修改会先给出建议，确认后再生效。"
            />
          }
        />
        <Route
          path="/settings"
          element={
            <PlaceholderPage
              title="设置"
              phase="后续阶段"
              summary="模型名称和 API 地址放在后端环境变量中。这个页面不会读取或保存密钥。"
            />
          }
        />
      </Route>
    </Routes>
  );
}
