// Recursive function patterns for cycle detection testing

// Direct recursion - simple factorial
export function factorial(n: number): number {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// Direct recursion - with accumulator
export function fibonacciTail(n: number, a: number = 0, b: number = 1): number {
    if (n === 0) return a;
    return fibonacciTail(n - 1, b, a + b);
}

// Indirect recursion - even/odd pattern
export function isEven(n: number): boolean {
    if (n === 0) return true;
    return isOdd(n - 1);
}

export function isOdd(n: number): boolean {
    if (n === 0) return false;
    return isEven(n - 1);
}

// Complex cycle - Three function cycle
export function processTaskA(data: any): void {
    console.log("Processing task A");
    if (data.needsB) {
        processTaskB(data);
    }
}

export function processTaskB(data: any): void {
    console.log("Processing task B");
    if (data.needsC) {
        processTaskC(data);
    }
}

export function processTaskC(data: any): void {
    console.log("Processing task C");
    if (data.needsA) {
        processTaskA(data); // Creates A → B → C → A cycle
    }
}

// Deep cycle - Five function chain
export function step1(counter: number): void {
    if (counter > 0) {
        step2(counter - 1);
    }
}

export function step2(counter: number): void {
    if (counter > 0) {
        step3(counter - 1);
    }
}

export function step3(counter: number): void {
    if (counter > 0) {
        step4(counter - 1);
    }
}

export function step4(counter: number): void {
    if (counter > 0) {
        step5(counter - 1);
    }
}

export function step5(counter: number): void {
    if (counter > 0) {
        step1(counter - 1); // Creates 5-function cycle
    }
}

// Mutual recursion with termination
export function parseExpression(input: string): ParseResult {
    const result = parseTerm(input);
    if (result.remaining.startsWith('+')) {
        return parseExpression(result.remaining.slice(1));
    }
    return result;
}

export function parseTerm(input: string): ParseResult {
    const result = parseFactor(input);
    if (result.remaining.startsWith('*')) {
        return parseTerm(result.remaining.slice(1));
    }
    return result;
}

export function parseFactor(input: string): ParseResult {
    if (input.startsWith('(')) {
        const result = parseExpression(input.slice(1));
        return {
            value: result.value,
            remaining: result.remaining.slice(1) // Skip closing ')'
        };
    }
    // Parse number
    const match = input.match(/^\d+/);
    if (match) {
        return {
            value: parseInt(match[0]),
            remaining: input.slice(match[0].length)
        };
    }
    throw new Error("Invalid input");
}

// Interface for parser
interface ParseResult {
    value: number;
    remaining: string;
}

// Self-referencing object method
export class RecursiveProcessor {
    private maxDepth: number = 10;
    
    public process(data: any, depth: number = 0): any {
        if (depth >= this.maxDepth) {
            return data;
        }
        
        if (Array.isArray(data)) {
            return data.map(item => this.process(item, depth + 1));
        }
        
        if (typeof data === 'object' && data !== null) {
            const result: any = {};
            for (const [key, value] of Object.entries(data)) {
                result[key] = this.process(value, depth + 1);
            }
            return result;
        }
        
        return data;
    }
    
    // Method that calls another method which might call back
    public validateAndProcess(data: any): any {
        if (this.isValid(data)) {
            return this.process(data);
        }
        throw new Error("Invalid data");
    }
    
    private isValid(data: any): boolean {
        if (typeof data === 'object' && data !== null) {
            // This could potentially call validateAndProcess on nested data
            return Object.values(data).every(value => 
                this.validateAndProcess(value) !== null
            );
        }
        return true;
    }
}

// Async recursive functions
export async function asyncRecursiveSearch(
    directory: string, 
    pattern: string,
    depth: number = 0
): Promise<string[]> {
    if (depth > 5) return [];
    
    const entries = await getDirectoryEntries(directory);
    const results: string[] = [];
    
    for (const entry of entries) {
        if (entry.isFile && entry.name.includes(pattern)) {
            results.push(entry.path);
        } else if (entry.isDirectory) {
            const subResults = await asyncRecursiveSearch(entry.path, pattern, depth + 1);
            results.push(...subResults);
        }
    }
    
    return results;
}

// Mock for async function
async function getDirectoryEntries(directory: string): Promise<DirectoryEntry[]> {
    return []; // Mock implementation
}

interface DirectoryEntry {
    name: string;
    path: string;
    isFile: boolean;
    isDirectory: boolean;
}