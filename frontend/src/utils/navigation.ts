export type NavItem = {
  to: string;
  label: string;
};

/** 侧边栏只放主要入口。带参数的详情页不放进导航。 */
export const navItems: NavItem[] = [
  { to: "/dashboard", label: "首页" },
  { to: "/goals", label: "学习目标" },
  { to: "/plans", label: "学习计划" },
  { to: "/tutor", label: "AI 导师" },
  { to: "/reviews", label: "复习" },
  { to: "/problems", label: "我的题库" },
  { to: "/problems/wrong", label: "错题本" },
  { to: "/progress", label: "学习档案" },
  { to: "/reports", label: "学习汇报" },
  { to: "/settings", label: "设置" },
];
