// Basic function calling patterns for call graph construction
export function login(username: string, password: string): boolean {
    const isValid = validateCredentials(username, password);
    if (isValid) {
        createSession(username);
        logSuccess(username);
        return true;
    } else {
        logFailure(username);
        return false;
    }
}

export function validateCredentials(username: string, password: string): boolean {
    const user = findUser(username);
    if (!user) {
        return false;
    }
    return hashPassword(password) === user.passwordHash;
}

export function createSession(username: string): void {
    const sessionId = generateSessionId();
    storeSession(sessionId, username);
    updateLastLogin(username);
}

export function findUser(username: string): User | null {
    return database.users.find(u => u.username === username) || null;
}

export function hashPassword(password: string): string {
    return crypto.sha256(password);
}

export function generateSessionId(): string {
    return Math.random().toString(36);
}

export function storeSession(sessionId: string, username: string): void {
    database.sessions.set(sessionId, { username, createdAt: new Date() });
}

export function updateLastLogin(username: string): void {
    const user = findUser(username);
    if (user) {
        user.lastLogin = new Date();
        database.users.save(user);
    }
}

export function logSuccess(username: string): void {
    console.log(`Login successful for ${username}`);
}

export function logFailure(username: string): void {
    console.log(`Login failed for ${username}`);
}

// Interface for testing
interface User {
    username: string;
    passwordHash: string;
    lastLogin: Date;
}

// Mock database for testing
const database = {
    users: {
        find: (predicate: (u: User) => boolean) => null as User | null,
        save: (user: User) => void 0
    },
    sessions: {
        set: (id: string, data: any) => void 0
    }
};

// Crypto mock
const crypto = {
    sha256: (input: string) => "hashed_" + input
};