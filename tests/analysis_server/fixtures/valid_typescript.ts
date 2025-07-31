// Valid TypeScript file for testing
export interface User {
    id: number;
    name: string;
    email: string;
}

export class UserService {
    private users: Map<number, User> = new Map();
    
    findById(id: number): User | null {
        return this.users.get(id) || null;
    }
    
    create(user: User): void {
        this.users.set(user.id, user);
    }
}

export function validateUser(user: User): boolean {
    return user.id > 0 && user.name.length > 0 && user.email.includes('@');
}

export const DEFAULT_USER: User = {
    id: 0,
    name: 'Guest',
    email: 'guest@example.com'
};