import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { Party, PartyMember } from '../types'

export function useParties() {
  return useQuery<Party[]>({
    queryKey: ['parties'],
    queryFn: () => api.get('/parties').then(r => r.data),
    staleTime: 2 * 60_000,
  })
}

export function useParty(id: string | undefined) {
  return useQuery<Party>({
    queryKey: ['parties', id],
    queryFn: () => api.get(`/parties/${id}`).then(r => r.data),
    enabled: !!id,
    staleTime: 2 * 60_000,
  })
}

export function usePartyMembers(id: string | undefined) {
  return useQuery<PartyMember[]>({
    queryKey: ['parties', id, 'members'],
    queryFn: () => api.get(`/parties/${id}/members`).then(r => r.data),
    enabled: !!id,
    staleTime: 2 * 60_000,
  })
}

export function usePartyPreview(inviteCode: string | undefined) {
  return useQuery<Party>({
    queryKey: ['party-preview', inviteCode],
    queryFn: () => api.get(`/parties/invite/${inviteCode}`).then(r => r.data),
    enabled: !!inviteCode,
    staleTime: 5 * 60_000,
  })
}

export function useCreateParty() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; tournament_id?: string }) =>
      api.post<Party>('/parties', body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parties'] })
    },
  })
}

export function useJoinParty() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (invite_code: string) =>
      api.post<Party>('/parties/join', { invite_code }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parties'] })
    },
  })
}

export function useLeaveParty() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (partyId: string) =>
      api.delete(`/parties/${partyId}/leave`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parties'] })
    },
  })
}
