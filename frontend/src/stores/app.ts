import { defineStore } from 'pinia'

export type RoleMode = 'student' | 'admin'

export interface CurrentUser {
  id: number
  student_id: string
  name: string
  role: RoleMode
  department: string
  class_name: string
}

export const useAppStore = defineStore('app', {
  state: () => ({
    roleMode: 'student' as RoleMode,
    studentId: 1,
    adminId: 3,
    currentUser: null as CurrentUser | null,
  }),
  actions: {
    switchRole(role: RoleMode) {
      this.roleMode = role
    },
    setCurrentUser(user: CurrentUser | null) {
      this.currentUser = user
      if (user?.role === 'admin') this.adminId = user.id
      if (user?.role === 'student') this.studentId = user.id
    },
  },
})
