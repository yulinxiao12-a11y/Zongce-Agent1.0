import { defineStore } from 'pinia'

export type RoleMode = 'student' | 'admin'

export const useAppStore = defineStore('app', {
  state: () => ({
    roleMode: 'student' as RoleMode,
    studentId: 1,
    adminId: 3,
  }),
  actions: {
    switchRole(role: RoleMode) {
      this.roleMode = role
    },
  },
})
