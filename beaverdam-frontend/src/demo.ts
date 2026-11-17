import type { AppSnapshot, Recommendation, Routine } from './types';
import { PROFILE_SHARING } from './types';
export const recommendations: Recommendation[] = [
  {id:'m1',name:'Alex Chen',initials:'AC',year:'2027',major:'Computer Science',bio:'Usually somewhere between a problem set, a pickup game, and a really good coffee.',interests:['Robotics','Tennis','Coffee'],categories:['academic','study'],strength:'Strong',color:'#e9dccc'},
  {id:'m2',name:'Jordan Rivera',initials:'JR',year:'2028',major:'Mechanical Engineering',bio:'Building things, finding good playlists, and exploring Boston on the weekends.',interests:['Design','Music','Running'],categories:['study','gym'],strength:'Strong',color:'#dce4cf'},
  {id:'m3',name:'Priya Shah',initials:'PS',year:'2027',major:'Mathematics',bio:'Math major, aspiring amateur chef, and enthusiastic board-game competitor.',interests:['Math','Board games','Cooking'],categories:['academic','dining'],strength:'Moderate',color:'#e6dce9'},
  {id:'m4',name:'Sam Okafor',initials:'SO',year:'2029',major:'Electrical Engineering',bio:'I like making music, learning new things, and meeting people outside my usual circles.',interests:['Live music','Engineering','Art'],categories:['academic','study'],strength:'Moderate',color:'#d9e7e4'},
  {id:'m5',name:'Taylor Kim',initials:'TK',year:'2028',major:'Biological Engineering',bio:'Always up for new projects, a gym buddy, or a post-class conversation.',interests:['Biology','Fitness','Hiking'],categories:['academic','gym'],strength:'Weak',color:'#f0dfd5'},
  {id:'m6',name:'Morgan Lee',initials:'ML',year:'2027',major:'Computer Science',bio:'A curious person who likes a good challenge and a long walk.',interests:['AI','Books','Photography'],categories:['academic','study'],strength:'Weak',color:'#e7e7cf'},
];
export const routines: Routine[] = [
  {id:'r1',title:'6.1210 Algorithms',category:'academic',day:'Monday',start:'11:00',end:'12:00',place:'Classroom',excluded:false},
  {id:'r2',title:'Study session',category:'study',day:'Tuesday',start:'14:00',end:'16:00',place:'Study space',excluded:false},
  {id:'r3',title:'Lunch break',category:'dining',day:'Wednesday',start:'12:00',end:'13:00',place:'Dining area',excluded:false},
  {id:'r4',title:'Workout',category:'gym',day:'Thursday',start:'17:00',end:'18:00',place:'Fitness center',excluded:false},
  {id:'r5',title:'Weekend hangout',category:'leisure',day:'Saturday',start:'15:00',end:'17:00',place:'Campus',excluded:false},
];
export const INITIAL_SNAPSHOT: AppSnapshot = {
  recommendations, routines,
  privacy:{sharing:{...PROFILE_SHARING.P2_no_dining},visibility:'everyone',hiddenRoutineIds:[],blindZones:[]},
  connections:{}
};
