import { User } from '../types/user';
import { AuthenticatedUser, GuestUser, BaseUser } from './user';

export class AuthService {
    private users: Map<number, AuthenticatedUser> = new Map();
    private currentUser: BaseUser | null = null;
    
    async authenticate(email: string, password: string): Promise<AuthenticatedUser | null> {
        const user = await this.validateCredentials(email, password);
        if (user) {
            this.currentUser = user;
            return user;
        }
        return null;
    }
    
    private async validateCredentials(email: string, password: string): Promise<AuthenticatedUser | null> {
        // Mock validation logic
        const user = this.findUserByEmail(email);
        return user && this.checkPassword(user, password) ? user : null;
    }
    
    private findUserByEmail(email: string): AuthenticatedUser | null {
        for (const user of this.users.values()) {
            if (user.email === email) {
                return user;
            }
        }
        return null;
    }
    
    private checkPassword(user: AuthenticatedUser, password: string): boolean {
        // Mock password validation
        return password.length >= 8;
    }
    
    getCurrentUser(): BaseUser | null {
        return this.currentUser;
    }
    
    logout(): void {
        this.currentUser = null;
    }
    
    createGuestUser(name: string): GuestUser {
        return new GuestUser(Date.now(), name);
    }
}