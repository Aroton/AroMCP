// Malformed TypeScript file for testing error handling
export interface User {
    id: number;
    name: string;
    email: string
    // Missing semicolon

export class UserService { // Missing closing brace for interface
    private users: Map<number, User> = new Map();
    
    findById(id: number): User | null {
        return this.users.get(id) || null;
    }
    
    create(user: User): void {
        this.users.set(user.id, user);
    // Missing closing brace

export function validateUser(user: User): boolean {
    return user.id > 0 && user.name.length > 0 && user.email.includes('@');
} // This function is fine

// Syntax error - invalid operator
const invalid = user +++ service;

// Missing closing brace for the file