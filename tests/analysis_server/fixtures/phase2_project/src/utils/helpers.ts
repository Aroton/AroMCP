import { User } from '../types/user';
import { AuthenticatedUser } from '../auth/user';

export function formatUserName(user: User): string {
    return user.name.trim().toLowerCase().replace(/\s+/g, '-');
}

export function isAuthenticatedUser(user: User): user is AuthenticatedUser {
    return 'getRole' in user && typeof (user as any).getRole === 'function';
}

export async function fetchUserData(userId: number): Promise<User | null> {
    try {
        const response = await fetch(`/api/users/${userId}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Failed to fetch user data:', error);
        return null;
    }
}

export const userUtils = {
    format: formatUserName,
    isAuthenticated: isAuthenticatedUser,
    fetch: fetchUserData
};