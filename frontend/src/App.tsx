import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./layouts/AppLayout.tsx";
import { DashboardPage } from "./pages/DashboardPage.tsx";
import { PlaceholderPage } from "./pages/PlaceholderPage.tsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route
          path="/goals"
          element={
            <PlaceholderPage
              title="学习目标"
              phase="第二阶段"
              summary="这里将创建、编辑、暂停和删除学习目标，并保存你目前掌握与尚未学习的内容。"
            />
          }
        />
        <Route
          path="/goals/:id"
          element={
            <PlaceholderPage
              title="学习目标详情"
              phase="第二阶段"
              summary="这里将查看某一个学习目标的资料和学习历史。"
            />
          }
        />
        <Route
          path="/plans"
          element={
            <PlaceholderPage
              title="学习计划"
              phase="第四阶段"
              summary="这里将展示总体路线、每日任务和计划调整记录。同一天已有计划时会直接读取，不会重复生成。"
            />
          }
        />
        <Route
          path="/learning/:lessonId"
          element={
            <PlaceholderPage
              title="AI 学习课堂"
              phase="第五阶段"
              summary="这里将按当天任务讲解知识点，并保留课程内容。"
            />
          }
        />
        <Route
          path="/quiz/:quizId"
          element={
            <PlaceholderPage
              title="知识测试"
              phase="第五阶段"
              summary="这里将逐题作答。客观题由后端按标准答案判分，结果写入数据库。"
            />
          }
        />
        <Route
          path="/progress"
          element={
            <PlaceholderPage
              title="学习档案"
              phase="第六阶段"
              summary="这里将汇总学习天数、正确率、知识点掌握情况和错题。历史记录会保留。"
            />
          }
        />
        <Route
          path="/reports"
          element={
            <PlaceholderPage
              title="学习汇报"
              phase="第六阶段"
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
