/**
 * Basic function signatures with simple types for Phase 3 testing.
 * Tests the most basic level of type resolution.
 */

export interface User {
    id: number;
    name: string;
    email: string;
    isActive: boolean;
}

export interface ApiResponse {
    success: boolean;
    message: string;
    timestamp: Date;
}

// Simple function declarations
export function createUser(name: string, email: string): User {
    return {
        id: Date.now(),
        name,
        email,
        isActive: true
    };
}

export function updateUserEmail(user: User, newEmail: string): User {
    return { ...user, email: newEmail };
}

export function isUserActive(user: User): boolean {
    return user.isActive;
}

// Arrow functions with explicit types
export const formatUserName = (user: User): string => {
    return `${user.name} <${user.email}>`;
};

export const validateEmail = (email: string): boolean => {
    return email.includes('@') && email.includes('.');
};

// Functions with optional parameters
export function getUserProfile(
    id: number,
    includeInactive?: boolean,
    format?: 'json' | 'xml'
): User | null {
    // Implementation would go here
    return null;
}

// Functions with default parameters
export function createApiResponse(
    success: boolean = true,
    message: string = 'Success',
    timestamp: Date = new Date()
): ApiResponse {
    return { success, message, timestamp };
}

// Functions with rest parameters
export function logMessages(level: 'info' | 'warn' | 'error', ...messages: string[]): void {
    console.log(`[${level.toUpperCase()}]:`, ...messages);
}

// Functions with union types
export function processUserInput(input: string | number | boolean): string {
    return String(input);
}

// Functions with array types
export function getActiveUsers(users: User[]): User[] {
    return users.filter(user => user.isActive);
}

export function getUserIds(users: User[]): number[] {
    return users.map(user => user.id);
}

// Functions with object literal types
export function createUserData(options: {
    name: string;
    email: string;
    role?: 'admin' | 'user';
    metadata?: Record<string, any>;
}): User {
    return {
        id: Date.now(),
        name: options.name,
        email: options.email,
        isActive: true
    };
}