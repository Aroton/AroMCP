/**
 * Advanced TypeScript type constructs for Phase 3 testing.
 * Tests the highest level of type resolution - full inference and complex types.
 */

// Template literal types
export type EventName<T extends string> = `on${Capitalize<T>}`;
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';
export type ApiEndpoint<Method extends HttpMethod, Path extends string> = 
    `${Method} ${Path}`;

// Conditional types with infer
export type ReturnTypeOf<T> = T extends (...args: any[]) => infer R ? R : never;
export type ParametersOf<T> = T extends (...args: infer P) => any ? P : never;
export type FirstParameter<T> = T extends (first: infer F, ...rest: any[]) => any ? F : never;

// Complex mapped types
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type MakeRequired<T, K extends keyof T> = T & Required<Pick<T, K>>;

export type DeepReadonly<T> = {
    readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
};

export type KeysOfType<T, U> = {
    [K in keyof T]: T[K] extends U ? K : never;
}[keyof T];

// Recursive type with constraints
export interface TreeNode<T> {
    value: T;
    children: TreeNode<T>[];
    parent?: TreeNode<T>;
}

export type Flatten<T> = T extends (infer U)[] 
    ? U extends (infer V)[]
        ? Flatten<V>
        : U
    : T;

// Complex function with template literals and conditionals
export function createEventHandler<T extends string>(
    eventType: T
): (handler: (event: { type: EventName<T>; data: any }) => void) => void {
    const eventName = `on${eventType.charAt(0).toUpperCase()}${eventType.slice(1)}` as EventName<T>;
    
    return (handler) => {
        // Implementation would register the handler
        console.log(`Registering handler for ${eventName}`);
    };
}

// Function with complex conditional return types
export function processData<T>(
    data: T
): T extends string 
    ? { text: string; length: number }
    : T extends number
    ? { value: number; formatted: string }
    : T extends boolean
    ? { flag: boolean; display: 'Yes' | 'No' }
    : { raw: T; type: string } {
    
    if (typeof data === 'string') {
        return { text: data, length: data.length } as any;
    } else if (typeof data === 'number') {
        return { value: data, formatted: data.toFixed(2) } as any;
    } else if (typeof data === 'boolean') {
        return { flag: data, display: data ? 'Yes' : 'No' } as any;
    } else {
        return { raw: data, type: typeof data } as any;
    }
}

// Function with complex inferred types
export function createValidator<T extends Record<string, any>>(
    schema: {
        [K in keyof T]: (value: unknown) => value is T[K];
    }
): (obj: unknown) => obj is T {
    return (obj): obj is T => {
        if (typeof obj !== 'object' || obj === null) return false;
        
        for (const key in schema) {
            if (!(key in obj) || !schema[key]((obj as any)[key])) {
                return false;
            }
        }
        return true;
    };
}

// Function with recursive types
export function traverseTree<T>(
    node: TreeNode<T>,
    visitor: (value: T, depth: number) => void,
    depth: number = 0
): void {
    visitor(node.value, depth);
    
    for (const child of node.children) {
        traverseTree(child, visitor, depth + 1);
    }
}

// Function with complex generic constraints and mapped types
export function transformObject<
    T extends Record<string, any>,
    K extends keyof T,
    U
>(
    obj: T,
    transformers: {
        [P in K]: (value: T[P]) => U;
    }
): {
    [P in keyof T]: P extends K ? U : T[P];
} {
    const result = { ...obj } as any;
    
    for (const key in transformers) {
        if (key in obj) {
            result[key] = transformers[key](obj[key]);
        }
    }
    
    return result;
}

// Function with higher-order types
export function createPipeline<T>(...functions: Array<(input: T) => T>): (input: T) => T {
    return (input: T) => functions.reduce((acc, fn) => fn(acc), input);
}

export function compose<T, U, V>(
    f: (input: U) => V,
    g: (input: T) => U
): (input: T) => V {
    return (input: T) => f(g(input));
}

// Function with discriminated unions
export type Shape = 
    | { type: 'circle'; radius: number }
    | { type: 'rectangle'; width: number; height: number }
    | { type: 'triangle'; base: number; height: number };

export function calculateArea(shape: Shape): number {
    switch (shape.type) {
        case 'circle':
            return Math.PI * shape.radius ** 2;
        case 'rectangle':
            return shape.width * shape.height;
        case 'triangle':
            return (shape.base * shape.height) / 2;
        default:
            const _exhaustive: never = shape;
            throw new Error(`Unknown shape type: ${_exhaustive}`);
    }
}

// Function with advanced pattern matching
export function handleResult<T, E>(
    result: { success: true; data: T } | { success: false; error: E }
): T | never {
    if (result.success) {
        return result.data;
    } else {
        throw new Error(`Operation failed: ${result.error}`);
    }
}

// Class with complex generic methods
export class AdvancedProcessor<T extends Record<string, any>> {
    private cache = new Map<string, any>();

    processWithCache<K extends keyof T, R>(
        key: K,
        value: T[K],
        processor: (val: T[K]) => R
    ): R {
        const cacheKey = `${String(key)}_${JSON.stringify(value)}`;
        
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }
        
        const result = processor(value);
        this.cache.set(cacheKey, result);
        return result;
    }

    batchProcess<K extends keyof T>(
        operations: Array<{
            key: K;
            value: T[K];
            processor: (val: T[K]) => any;
        }>
    ): Map<K, any> {
        const results = new Map<K, any>();
        
        for (const op of operations) {
            results.set(op.key, this.processWithCache(op.key, op.value, op.processor));
        }
        
        return results;
    }
}

// Function with complex async patterns
export async function processWithRetry<T, U>(
    operation: () => Promise<T>,
    retries: number = 3,
    transform?: (result: T) => U
): Promise<U extends undefined ? T : U> {
    let lastError: Error | undefined;
    
    for (let i = 0; i <= retries; i++) {
        try {
            const result = await operation();
            return (transform ? transform(result) : result) as any;
        } catch (error) {
            lastError = error as Error;
            if (i < retries) {
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
            }
        }
    }
    
    throw lastError || new Error('Operation failed after retries');
}