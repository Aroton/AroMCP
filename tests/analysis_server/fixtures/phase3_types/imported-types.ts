/**
 * Functions using imported interfaces and types for Phase 3 testing.
 * Tests type resolution across module boundaries.
 */

import { User, ApiResponse } from './basic-types';
import { BaseEntity, Repository } from './generic-functions';
import { Shape, TreeNode } from './complex-types';
import type { HttpMethod, EventName } from './complex-types';

// Re-exports for testing import resolution
export { User, BaseEntity } from './basic-types';
export type { ApiResponse } from './basic-types';

// Local interfaces that extend imported ones
export interface ExtendedUser extends User {
    preferences: {
        theme: 'light' | 'dark';
        language: string;
        notifications: boolean;
    };
    lastLoginAt?: Date;
}

export interface UserRepository extends Repository<User> {
    findByEmail(email: string): Promise<User | null>;
    findActiveUsers(): Promise<User[]>;
}

// Functions using imported types
export function createExtendedUser(
    baseUser: User,
    preferences: ExtendedUser['preferences']
): ExtendedUser {
    return {
        ...baseUser,
        preferences,
        lastLoginAt: new Date()
    };
}

export function validateApiResponse<T>(
    response: ApiResponse<T>,
    validator: (data: T) => boolean
): T | null {
    if (!response.success || !response.data) {
        return null;
    }
    
    return validator(response.data) ? response.data : null;
}

// Function with complex imported generic constraints
export function processUserEntities<T extends BaseEntity & { email: string }>(
    entities: T[],
    emailProcessor: (email: string) => string
): T[] {
    return entities.map(entity => ({
        ...entity,
        email: emailProcessor(entity.email),
        updatedAt: new Date()
    }));
}

// Function using imported template literal types
export function createHttpEndpoint<M extends HttpMethod>(
    method: M,
    path: string,
    handler: (req: any, res: any) => void
): { endpoint: `${M} ${string}`; handler: Function } {
    return {
        endpoint: `${method} ${path}` as `${M} ${string}`,
        handler
    };
}

// Function using imported recursive types
export function findInTree<T>(
    root: TreeNode<T>,
    predicate: (value: T) => boolean
): TreeNode<T> | null {
    if (predicate(root.value)) {
        return root;
    }
    
    for (const child of root.children) {
        const found = findInTree(child, predicate);
        if (found) return found;
    }
    
    return null;
}

// Function with imported discriminated union
export function getShapeInfo(shape: Shape): {
    type: string;
    area: number;
    perimeter: number;
} {
    switch (shape.type) {
        case 'circle':
            return {
                type: 'circle',
                area: Math.PI * shape.radius ** 2,
                perimeter: 2 * Math.PI * shape.radius
            };
        case 'rectangle':
            return {
                type: 'rectangle',
                area: shape.width * shape.height,
                perimeter: 2 * (shape.width + shape.height)
            };
        case 'triangle':
            return {
                type: 'triangle',
                area: (shape.base * shape.height) / 2,
                perimeter: shape.base + 2 * Math.sqrt((shape.base/2)**2 + shape.height**2)
            };
    }
}

// Complex function using multiple imported types
export class UserService {
    constructor(private repository: UserRepository) {}

    async createUserWithValidation(
        userData: Omit<User, 'id'>,
        validator: (user: User) => boolean
    ): Promise<ApiResponse<ExtendedUser>> {
        try {
            const user: User = {
                id: Date.now(),
                ...userData
            };

            if (!validator(user)) {
                return {
                    success: false,
                    data: null,
                    error: 'User validation failed'
                };
            }

            const extendedUser = createExtendedUser(user, {
                theme: 'light',
                language: 'en',
                notifications: true
            });

            await this.repository.save(extendedUser);

            return {
                success: true,
                data: extendedUser
            };
        } catch (error) {
            return {
                success: false,
                data: null,
                error: error instanceof Error ? error.message : 'Unknown error'
            };
        }
    }

    async processUserBatch<T extends User>(
        users: T[],
        processor: (user: T) => Promise<T>
    ): Promise<ApiResponse<T[]>> {
        try {
            const processedUsers = await Promise.all(
                users.map(user => processor(user))
            );

            return {
                success: true,
                data: processedUsers
            };
        } catch (error) {
            return {
                success: false,
                data: null,
                error: error instanceof Error ? error.message : 'Batch processing failed'
            };
        }
    }
}

// Function with conditional imports (dynamic)
export async function loadUserProcessor(
    processorType: 'basic' | 'advanced'
): Promise<(user: User) => Promise<User>> {
    if (processorType === 'advanced') {
        // Dynamic import simulation
        const { AdvancedProcessor } = await import('./complex-types');
        const processor = new AdvancedProcessor<User>();
        
        return async (user: User) => {
            return processor.processWithCache('name', user.name, (name) => ({
                ...user,
                name: name.toUpperCase()
            }));
        };
    } else {
        return async (user: User) => user;
    }
}

// Function testing namespace imports
import * as BasicTypes from './basic-types';

export function processAllBasicTypes(data: {
    user: BasicTypes.User;
    response: BasicTypes.ApiResponse;
}): string {
    const formatter = BasicTypes.formatUserName(data.user);
    return `User: ${formatter}, Success: ${data.response.success}`;
}

// Function with type-only imports
export function createEventName<T extends string>(
    eventType: T
): EventName<T> {
    return `on${eventType.charAt(0).toUpperCase()}${eventType.slice(1)}` as EventName<T>;
}