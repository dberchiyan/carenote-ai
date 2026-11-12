export const authKeys = {
  me: () => ["auth", "me"] as const,
  demoUsers: () => ["auth", "demo-users"] as const,
};
