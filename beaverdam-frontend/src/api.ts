import { INITIAL_SNAPSHOT } from './demo';
import type { AppSnapshot, PrivacySettings, Recommendation, Routine, ConnectState, ChatMessage, Conversation } from './types';
/** Server adapter for a future production backend. DEMO MODE is explicit; no check-in data is uploaded. */
const ROOT = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '');
export const DEMO_MODE = !ROOT;
async function request<T>(path:string, init?: RequestInit):Promise<T> {
  if (!ROOT) throw new Error('API not configured');
  const result = await fetch(`${ROOT}${path}`, {credentials:'include',headers:{'Content-Type':'application/json'}, ...init});
  if (!result.ok) throw new Error(`Server request failed (${result.status})`);
  return result.json() as Promise<T>;
}
export const api = {
  async load():Promise<AppSnapshot> { return DEMO_MODE ? structuredClone(INITIAL_SNAPSHOT) : request<AppSnapshot>('/api/v1/me/dashboard'); },
  async savePrivacy(privacy:PrivacySettings):Promise<PrivacySettings> {return DEMO_MODE ? privacy : request('/api/v1/me/privacy',{method:'PUT',body:JSON.stringify(privacy)});},
  async saveRoutines(routines:Routine[]):Promise<Routine[]> {return DEMO_MODE ? routines : request('/api/v1/me/routines',{method:'PUT',body:JSON.stringify(routines)});},
  async refreshRecommendations():Promise<Recommendation[]> {return DEMO_MODE ? structuredClone(INITIAL_SNAPSHOT.recommendations) : request('/api/v1/me/recommendations');},
  async selectDemo(student:string,dataset:string):Promise<AppSnapshot> {return DEMO_MODE ? structuredClone(INITIAL_SNAPSHOT) : request('/api/v1/demo/select',{method:'POST',body:JSON.stringify({student,dataset})});},
  async conversations():Promise<Conversation[]> {return DEMO_MODE ? [] : request('/api/v1/me/conversations');},
  async messages(id:string):Promise<{student:string;messages:ChatMessage[]}> {return DEMO_MODE ? {student:id,messages:[]} : request(`/api/v1/messages/${encodeURIComponent(id)}`);},
  async sendMessage(id:string,text:string):Promise<ChatMessage> {return request(`/api/v1/messages/${encodeURIComponent(id)}`,{method:'POST',body:JSON.stringify({text})});},
  async connect(id:string):Promise<{state:ConnectState}> {return DEMO_MODE ? {state:'requested'} : request(`/api/v1/connections/${encodeURIComponent(id)}`,{method:'POST'});},
};
