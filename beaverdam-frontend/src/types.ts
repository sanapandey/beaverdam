export const CATEGORIES = ['academic', 'study', 'dining', 'gym', 'leisure'] as const;
export type Category = typeof CATEGORIES[number];
export type Sharing = Record<Category, boolean>;
export const PROFILE_SHARING: Record<string, Sharing> = {
  P1_all_but_leisure: { academic: true, study: true, dining: true, gym: true, leisure: false },
  P2_no_dining: { academic: true, study: true, dining: false, gym: true, leisure: false },
  P3_no_dining_gym: { academic: true, study: true, dining: false, gym: false, leisure: false },
  P4_academic_only: { academic: true, study: false, dining: false, gym: false, leisure: false },
};
export type MatchLabel = 'Strong' | 'Moderate' | 'Weak';
export type Recommendation = { id: string; name: string; initials: string; year: string; major: string; bio: string; interests: string[]; categories: Category[]; strength: MatchLabel; color: string };
export type Routine = { id: string; title: string; category: Category; day: string; start: string; end: string; place: string; excluded: boolean };
export type BlindZone = { id: string; label: string; kind: 'Place' | 'Time'; value: string };
export type PrivacySettings = { sharing: Sharing; visibility: 'everyone' | 'recommended' | 'hidden'; hiddenRoutineIds: string[]; blindZones: BlindZone[] };
export type ConnectState = 'none' | 'requested' | 'incoming' | 'connected';
export interface AppSnapshot { recommendations: Recommendation[]; routines: Routine[]; privacy: PrivacySettings; connections: Record<string, ConnectState>; demo?: {student: string; dataset:string; datasets:string[]} }

export type ChatMessage = { id:string; sender:string; text:string; createdAt:string };
export type Conversation = { student:string; lastMessage:ChatMessage|null; messageCount:number };
