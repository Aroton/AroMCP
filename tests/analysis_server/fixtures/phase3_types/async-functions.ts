/**
 * Async functions and Promise types for Phase 3 testing.
 * Tests async/await patterns and Promise type resolution.
 */

import { User, ApiResponse } from './basic-types';
import { BaseEntity } from './generic-functions';

// Simple async functions
export async function fetchUser(id: number): Promise<User | null> {
    try {
        const response = await fetch(`/api/users/${id}`);
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        return null;
    }
}

export async function saveUser(user: User): Promise<boolean> {
    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(user)
        });
        return response.ok;
    } catch (error) {
        return false;
    }
}

// Generic async functions
export async function fetchEntity<T extends BaseEntity>(
    endpoint: string,
    id: string
): Promise<T | null> {
    try {
        const response = await fetch(`${endpoint}/${id}`);
        if (!response.ok) return null;
        return await response.json() as T;
    } catch (error) {
        return null;
    }
}

export async function saveEntity<T extends BaseEntity>(
    endpoint: string,
    entity: T
): Promise<ApiResponse<T>> {
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(entity)
        });
        
        if (!response.ok) {
            return {
                success: false,
                data: null,
                error: `HTTP ${response.status}: ${response.statusText}`
            };
        }
        
        const data = await response.json() as T;
        return {
            success: true,
            data
        };
    } catch (error) {
        return {
            success: false,
            data: null,
            error: error instanceof Error ? error.message : 'Unknown error'
        };
    }
}

// Async functions with Promise.all
export async function fetchMultipleUsers(ids: number[]): Promise<User[]> {
    const promises = ids.map(id => fetchUser(id));
    const results = await Promise.all(promises);
    return results.filter((user): user is User => user !== null);
}

export async function batchSaveUsers(users: User[]): Promise<{
    successful: User[];
    failed: { user: User; error: string }[];
}> {
    const results = await Promise.allSettled(
        users.map(async (user) => {
            const success = await saveUser(user);
            if (!success) {
                throw new Error(`Failed to save user ${user.id}`);
            }
            return user;
        })
    );
    
    const successful: User[] = [];
    const failed: { user: User; error: string }[] = [];
    
    results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
            successful.push(result.value);
        } else {
            failed.push({
                user: users[index],
                error: result.reason?.message || 'Unknown error'
            });
        }
    });
    
    return { successful, failed };
}

// Async functions with Promise.race
export async function fetchUserWithTimeout(
    id: number,
    timeoutMs: number = 5000
): Promise<User | null> {
    const fetchPromise = fetchUser(id);
    const timeoutPromise = new Promise<null>((_, reject) => {
        setTimeout(() => reject(new Error('Request timeout')), timeoutMs);
    });
    
    try {
        return await Promise.race([fetchPromise, timeoutPromise]);
    } catch (error) {
        return null;
    }
}

// Async generator functions
export async function* fetchUsersPaginated(
    pageSize: number = 10
): AsyncGenerator<User[], void, unknown> {
    let page = 1;
    let hasMore = true;
    
    while (hasMore) {
        const response = await fetch(`/api/users?page=${page}&limit=${pageSize}`);
        
        if (!response.ok) {
            throw new Error(`Failed to fetch page ${page}`);
        }
        
        const data = await response.json() as {
            users: User[];
            hasMore: boolean;
        };
        
        yield data.users;
        hasMore = data.hasMore;
        page++;
    }
}

export async function* processUsersStream<T>(
    users: AsyncIterable<User[]>,
    processor: (user: User) => Promise<T>
): AsyncGenerator<T[], void, unknown> {
    for await (const userBatch of users) {
        const processedBatch = await Promise.all(
            userBatch.map(user => processor(user))
        );
        yield processedBatch;
    }
}

// Complex async patterns with retries
export async function fetchWithRetry<T>(
    fetcher: () => Promise<T>,
    maxRetries: number = 3,
    delayMs: number = 1000
): Promise<T> {
    let lastError: Error;
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            return await fetcher();
        } catch (error) {
            lastError = error as Error;
            
            if (attempt < maxRetries) {
                await new Promise(resolve => 
                    setTimeout(resolve, delayMs * Math.pow(2, attempt))
                );
            }
        }
    }
    
    throw lastError!;
}

// Async functions with complex error handling
export async function processUserSafely<T>(
    user: User,
    processor: (user: User) => Promise<T>
): Promise<{ success: true; data: T } | { success: false; error: string }> {
    try {
        const data = await processor(user);
        return { success: true, data };
    } catch (error) {
        return {
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        };
    }
}

// Async class with Promise-based methods
export class AsyncUserService {
    private cache = new Map<number, Promise<User | null>>();
    
    async getUser(id: number, useCache: boolean = true): Promise<User | null> {
        if (useCache && this.cache.has(id)) {
            return this.cache.get(id)!;
        }
        
        const promise = this.fetchUserFromAPI(id);
        
        if (useCache) {
            this.cache.set(id, promise);
        }
        
        return promise;
    }
    
    private async fetchUserFromAPI(id: number): Promise<User | null> {
        return fetchUser(id);
    }
    
    async createUser(userData: Omit<User, 'id'>): Promise<User> {
        const user: User = {
            id: Date.now(),
            ...userData
        };
        
        const success = await saveUser(user);
        
        if (!success) {
            throw new Error('Failed to create user');
        }
        
        // Cache the new user
        this.cache.set(user.id, Promise.resolve(user));
        
        return user;
    }
    
    async updateUser(id: number, updates: Partial<User>): Promise<User | null> {
        const existingUser = await this.getUser(id);
        
        if (!existingUser) {
            return null;
        }
        
        const updatedUser = { ...existingUser, ...updates };
        const success = await saveUser(updatedUser);
        
        if (!success) {
            throw new Error('Failed to update user');
        }
        
        // Update cache
        this.cache.set(id, Promise.resolve(updatedUser));
        
        return updatedUser;
    }
    
    async batchProcessUsers<T>(
        userIds: number[],
        processor: (user: User) => Promise<T>,
        concurrency: number = 5
    ): Promise<Array<{ id: number; result: T | null; error?: string }>> {
        const results: Array<{ id: number; result: T | null; error?: string }> = [];
        
        // Process in chunks to limit concurrency
        for (let i = 0; i < userIds.length; i += concurrency) {
            const chunk = userIds.slice(i, i + concurrency);
            
            const chunkPromises = chunk.map(async (id) => {
                try {
                    const user = await this.getUser(id);
                    if (!user) {
                        return { id, result: null, error: 'User not found' };
                    }
                    
                    const result = await processor(user);
                    return { id, result };
                } catch (error) {
                    return {
                        id,
                        result: null,
                        error: error instanceof Error ? error.message : 'Unknown error'
                    };
                }
            });
            
            const chunkResults = await Promise.all(chunkPromises);
            results.push(...chunkResults);
        }
        
        return results;
    }
}

// Advanced async patterns with conditional promises
export async function conditionalFetch<T, U>(
    condition: boolean,
    fetchTrue: () => Promise<T>,
    fetchFalse: () => Promise<U>
): Promise<T | U> {
    return condition ? await fetchTrue() : await fetchFalse();
}

// Async function with complex Promise chains
export async function processUserWorkflow(
    userId: number
): Promise<{
    user: User;
    processed: boolean;
    notifications: string[];
}> {
    const user = await fetchUser(userId);
    
    if (!user) {
        throw new Error('User not found');
    }
    
    // Chain of async operations
    const processedUser = await saveUser(user)
        .then(async (saved) => {
            if (!saved) throw new Error('Save failed');
            return user;
        })
        .then(async (user) => {
            // Simulate additional processing
            await new Promise(resolve => setTimeout(resolve, 100));
            return user;
        });
    
    const notifications = await Promise.all([
        Promise.resolve(`Welcome ${processedUser.name}!`),
        Promise.resolve(`Email sent to ${processedUser.email}`),
        new Promise<string>(resolve => 
            setTimeout(() => resolve('Background process completed'), 50)
        )
    ]);
    
    return {
        user: processedUser,
        processed: true,
        notifications
    };
}