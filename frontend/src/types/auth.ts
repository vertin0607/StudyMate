/** 与后端 UserPublic 一致。不含密码和会话令牌。 */
export type AuthUser = {
  id: number;
  username: string;
  email: string | null;
  nickname: string;
  avatar: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
