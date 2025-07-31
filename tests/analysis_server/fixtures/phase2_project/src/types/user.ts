import { Entity, Status } from './base';

export interface User {
    id: number;
    name: string;
    email: string;
    profile?: UserProfile;
}

export interface UserProfile {
    avatar: string;
    bio: string;
    preferences: UserPreferences;
}

export interface UserPreferences {
    theme: 'light' | 'dark';
    notifications: boolean;
}

export type UserWithProfile = User & {
    profile: UserProfile;
};

export enum UserRole {
    ADMIN = 'admin',
    USER = 'user',
    MODERATOR = 'moderator'
}