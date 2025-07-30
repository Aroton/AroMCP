/**
 * Functions with TypeScript utility types and mapped types for Phase 3 testing.
 * Tests advanced type system features and utility type resolution.
 */

// Base interfaces for testing utility types
export interface DatabaseEntity {
    id: string;
    createdAt: Date;
    updatedAt: Date;
    version: number;
}

export interface UserData {
    name: string;
    email: string;
    age: number;
    isActive: boolean;
    role: 'admin' | 'user' | 'guest';
    metadata: {
        lastLogin?: Date;
        preferences: {
            theme: 'light' | 'dark';
            language: string;
        };
    };
}

export interface ApiConfig {
    baseUrl: string;
    timeout: number;
    retries: number;
    headers: Record<string, string>;
    authentication: {
        type: 'bearer' | 'api_key' | 'basic';
        credentials: string;
    };
}

// Functions using Partial<T>
export function updateUserData(
    current: UserData,
    updates: Partial<UserData>
): UserData {
    return { ...current, ...updates };
}

export function createUserDefaults(
    overrides?: Partial<UserData>
): UserData {
    const defaults: UserData = {
        name: '',
        email: '',
        age: 0,
        isActive: true,
        role: 'user',
        metadata: {
            preferences: {
                theme: 'light',
                language: 'en'
            }
        }
    };
    
    return { ...defaults, ...overrides };
}

// Functions using Required<T>
export function validateCompleteUser(
    user: Partial<UserData>
): user is Required<UserData> {
    return !!(
        user.name &&
        user.email &&
        user.age !== undefined &&
        user.isActive !== undefined &&
        user.role &&
        user.metadata
    );
}

export function processCompleteUser(
    user: Required<UserData>
): string {
    return `${user.name} (${user.email}) - Age: ${user.age}`;
}

// Functions using Pick<T, K>
export function extractUserProfile(
    user: UserData
): Pick<UserData, 'name' | 'email' | 'age'> {
    return {
        name: user.name,
        email: user.email,
        age: user.age
    };
}

export function getApiConnectionInfo(
    config: ApiConfig
): Pick<ApiConfig, 'baseUrl' | 'timeout'> {
    return {
        baseUrl: config.baseUrl,
        timeout: config.timeout
    };
}

// Functions using Omit<T, K>
export function createPublicUserData(
    user: UserData
): Omit<UserData, 'metadata' | 'isActive'> {
    return {
        name: user.name,
        email: user.email,
        age: user.age,
        role: user.role
    };
}

export function sanitizeApiConfig(
    config: ApiConfig
): Omit<ApiConfig, 'authentication'> {
    return {
        baseUrl: config.baseUrl,
        timeout: config.timeout,
        retries: config.retries,
        headers: config.headers
    };
}

// Functions using Record<K, T>
export function createUserLookup(
    users: UserData[]
): Record<string, UserData> {
    return users.reduce((lookup, user) => {
        lookup[user.email] = user;
        return lookup;
    }, {} as Record<string, UserData>);
}

export function validateFieldTypes(
    data: Record<string, unknown>
): Record<string, string> {
    const types: Record<string, string> = {};
    
    for (const [key, value] of Object.entries(data)) {
        types[key] = typeof value;
    }
    
    return types;
}

// Functions using Exclude<T, U>
export type NonAdminRole = Exclude<UserData['role'], 'admin'>;

export function assignNonAdminRole(
    role: NonAdminRole
): { role: NonAdminRole; permissions: string[] } {
    return {
        role,
        permissions: role === 'user' ? ['read', 'write'] : ['read']
    };
}

// Functions using Extract<T, U>
export type NumericValues = Extract<keyof UserData, 'age'>;

export function getNumericUserFields(
    user: UserData
): Pick<UserData, NumericValues> {
    return { age: user.age };
}

// Functions using NonNullable<T>
export function processDefinedValue<T>(
    value: T | null | undefined
): NonNullable<T> | never {
    if (value === null || value === undefined) {
        throw new Error('Value cannot be null or undefined');
    }
    return value;
}

// Functions using ReturnType<T>
export function createUser(): UserData {
    return createUserDefaults();
}

export type CreateUserResult = ReturnType<typeof createUser>;

export function processCreateUserResult(
    result: CreateUserResult
): string {
    return `Created user: ${result.name}`;
}

// Functions using Parameters<T>
export function logFunctionCall<T extends (...args: any[]) => any>(
    fn: T,
    ...args: Parameters<T>
): ReturnType<T> {
    console.log(`Calling function with args:`, args);
    return fn(...args);
}

// Functions using ConstructorParameters<T>
export class UserProcessor {
    constructor(
        public config: ApiConfig,
        public defaultRole: UserData['role'] = 'user'
    ) {}
    
    process(user: UserData): UserData {
        return { ...user, role: this.defaultRole };
    }
}

export function createUserProcessor(
    ...args: ConstructorParameters<typeof UserProcessor>
): UserProcessor {
    return new UserProcessor(...args);
}

// Functions using InstanceType<T>
export type ProcessorInstance = InstanceType<typeof UserProcessor>;

export function configureProcessor(
    processor: ProcessorInstance,
    newConfig: Partial<ApiConfig>
): ProcessorInstance {
    processor.config = { ...processor.config, ...newConfig };
    return processor;
}

// Functions using conditional types
export type ApiResult<T> = T extends string
    ? { text: T; length: number }
    : T extends number
    ? { value: T; formatted: string }
    : { data: T };

export function formatApiResult<T>(input: T): ApiResult<T> {
    if (typeof input === 'string') {
        return { text: input, length: input.length } as ApiResult<T>;
    } else if (typeof input === 'number') {
        return { value: input, formatted: input.toFixed(2) } as ApiResult<T>;
    } else {
        return { data: input } as ApiResult<T>;
    }
}

// Functions using mapped types
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export function updateOptionalFields<T, K extends keyof T>(
    obj: T,
    updates: Partial<Pick<T, K>>
): MakeOptional<T, K> {
    return { ...obj, ...updates } as MakeOptional<T, K>;
}

// Functions using template literal types
export type FieldValidatorName<T extends string> = `validate${Capitalize<T>}`;

export function createFieldValidator<T extends string>(
    fieldName: T
): { [K in FieldValidatorName<T>]: (value: any) => boolean } {
    const validatorName = `validate${fieldName.charAt(0).toUpperCase()}${fieldName.slice(1)}` as FieldValidatorName<T>;
    
    return {
        [validatorName]: (value: any) => value !== null && value !== undefined
    } as { [K in FieldValidatorName<T>]: (value: any) => boolean };
}

// Complex utility type combinations
export type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export function mergeDeepPartial<T>(
    target: T,
    source: DeepPartial<T>
): T {
    const result = { ...target };
    
    for (const key in source) {
        if (source[key] !== undefined) {
            if (typeof source[key] === 'object' && source[key] !== null) {
                (result as any)[key] = mergeDeepPartial(
                    (target as any)[key] || {},
                    source[key] as any
                );
            } else {
                (result as any)[key] = source[key];
            }
        }
    }
    
    return result;
}

// Function with complex utility type chain
export function processUserWithUtilities(
    partialUser: Partial<UserData>,
    requiredFields: Array<keyof UserData>,
    omitFields: Array<keyof UserData>
): Omit<Required<UserData>, (typeof omitFields)[number]> | null {
    
    // Validate required fields are present
    for (const field of requiredFields) {
        if (partialUser[field] === undefined) {
            return null;
        }
    }
    
    const completeUser = partialUser as Required<UserData>;
    const result = { ...completeUser };
    
    // Remove omitted fields
    for (const field of omitFields) {
        delete (result as any)[field];
    }
    
    return result as Omit<Required<UserData>, (typeof omitFields)[number]>;
}