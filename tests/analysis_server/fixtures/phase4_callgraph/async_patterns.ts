// Async patterns and Promise chains for call graph testing

export async function complexAsyncWorkflow(userId: string): Promise<UserProfile> {
    // Sequential async calls
    const user = await fetchUser(userId);
    const preferences = await fetchUserPreferences(user.id);
    const permissions = await fetchUserPermissions(user.id);
    
    // Parallel async calls
    const [orders, recommendations, notifications] = await Promise.all([
        fetchUserOrders(user.id),
        generateRecommendations(user, preferences),
        fetchNotifications(user.id)
    ]);
    
    // Conditional async calls
    if (user.isPremium) {
        const premiumData = await fetchPremiumData(user.id);
        const analyticsData = await fetchAnalytics(user.id);
        return buildPremiumProfile(user, preferences, permissions, orders, recommendations, notifications, premiumData, analyticsData);
    } else {
        return buildBasicProfile(user, preferences, permissions, orders, recommendations, notifications);
    }
}

export async function promiseChaining(data: InputData): Promise<ProcessedResult> {
    return validateInput(data)
        .then(validatedData => preprocessData(validatedData))
        .then(preprocessedData => transformData(preprocessedData))
        .then(transformedData => enrichData(transformedData))
        .then(enrichedData => finalizeData(enrichedData))
        .catch(error => handleProcessingError(error));
}

export async function asyncErrorHandling(operation: string): Promise<OperationResult> {
    try {
        const step1 = await performStep1(operation);
        const step2 = await performStep2(step1);
        const step3 = await performStep3(step2);
        return await finalizeOperation(step3);
    } catch (error) {
        if (error instanceof NetworkError) {
            await logNetworkError(error);
            return retryOperation(operation);
        } else if (error instanceof ValidationError) {
            await logValidationError(error);
            return handleValidationFailure(operation);
        } else {
            await logUnknownError(error);
            throw new ProcessingError('Operation failed', error);
        }
    }
}

export function callbackPatterns(data: CallbackData, callback: (result: any) => void): void {
    // Traditional callback pattern
    processDataAsync(data, (error, result) => {
        if (error) {
            handleCallbackError(error);
            callback(null);
        } else {
            transformResult(result, (transformError, transformedResult) => {
                if (transformError) {
                    handleTransformError(transformError);
                    callback(null);
                } else {
                    finalizeResult(transformedResult, callback);
                }
            });
        }
    });
}

export async function asyncGeneratorPattern(): AsyncGenerator<ProcessedItem, void, unknown> {
    const items = await fetchItemsToProcess();
    
    for (const item of items) {
        const processedItem = await processItemAsync(item);
        if (processedItem.isValid) {
            yield processedItem;
        }
        
        // Conditional yield with async call
        if (item.requiresSpecialHandling) {
            const specialResult = await applySpecialProcessing(item);
            yield specialResult;
        }
    }
    
    // Final cleanup
    await cleanupProcessing();
}

export async function racingPromises(sources: DataSource[]): Promise<FirstSuccessResult> {
    // Promise.race with fallback logic
    try {
        const fastestResult = await Promise.race(
            sources.map(source => fetchFromSource(source))
        );
        return processRaceWinner(fastestResult);
    } catch (firstError) {
        // If race fails, try Promise.allSettled for fallback
        const allResults = await Promise.allSettled(
            sources.map(source => fetchFromSourceWithRetry(source))
        );
        
        const successfulResults = allResults
            .filter(result => result.status === 'fulfilled')
            .map(result => (result as PromiseFulfilledResult<any>).value);
            
        if (successfulResults.length > 0) {
            return processFallbackResults(successfulResults);
        } else {
            throw new AllSourcesFailedError('All data sources failed');
        }
    }
}

export async function dynamicAsyncCalls(config: DynamicConfig): Promise<DynamicResult> {
    const results: any[] = [];
    
    // Dynamic method calls based on config
    for (const step of config.processingSteps) {
        switch (step.type) {
            case 'fetch':
                const fetchResult = await dynamicFetch(step.source);
                results.push(fetchResult);
                break;
            case 'transform':
                const transformResult = await dynamicTransform(step.transformer, results);
                results.push(transformResult);
                break;
            case 'validate':
                const isValid = await dynamicValidate(step.validator, results);
                if (!isValid) {
                    throw new ValidationError(`Step ${step.name} validation failed`);
                }
                break;
            case 'aggregate':
                const aggregated = await dynamicAggregate(step.aggregator, results);
                results.push(aggregated);
                break;
            default:
                await handleUnknownStepType(step);
        }
    }
    
    return combineDynamicResults(results);
}

export class AsyncServiceManager {
    private services: Map<string, AsyncService> = new Map();
    
    async initializeServices(serviceConfigs: ServiceConfig[]): Promise<void> {
        // Parallel service initialization
        const initPromises = serviceConfigs.map(async config => {
            const service = await createService(config);
            await service.initialize();
            this.services.set(config.name, service);
            return service;
        });
        
        await Promise.all(initPromises);
        
        // Post-initialization setup
        await this.setupServiceConnections();
        await this.validateServiceHealth();
    }
    
    async executeServiceWorkflow(workflowName: string, input: any): Promise<any> {
        const workflow = await this.getWorkflow(workflowName);
        let currentData = input;
        
        for (const step of workflow.steps) {
            const service = this.services.get(step.serviceName);
            if (!service) {
                throw new ServiceNotFoundError(`Service ${step.serviceName} not found`);
            }
            
            // Conditional service calls
            if (step.condition && !await this.evaluateCondition(step.condition, currentData)) {
                continue;
            }
            
            // Execute service method dynamically
            const methodName = step.method;
            const serviceMethod = (service as any)[methodName];
            if (!serviceMethod) {
                throw new MethodNotFoundError(`Method ${methodName} not found on service ${step.serviceName}`);
            }
            
            currentData = await serviceMethod.call(service, currentData, step.parameters);
            
            // Error handling with retries
            if (step.retryOnFailure && !currentData.success) {
                currentData = await this.retryServiceCall(service, methodName, currentData, step.parameters);
            }
        }
        
        return currentData;
    }
    
    private async setupServiceConnections(): Promise<void> {
        for (const [name, service] of this.services) {
            await service.connect();
            await this.registerServiceCallbacks(name, service);
        }
    }
    
    private async validateServiceHealth(): Promise<void> {
        const healthChecks = Array.from(this.services.entries()).map(
            async ([name, service]) => {
                const isHealthy = await service.healthCheck();
                if (!isHealthy) {
                    await this.handleUnhealthyService(name, service);
                }
                return { name, isHealthy };
            }
        );
        
        const results = await Promise.allSettled(healthChecks);
        await this.processHealthCheckResults(results);
    }
    
    private async retryServiceCall(
        service: AsyncService, 
        methodName: string, 
        data: any, 
        parameters: any
    ): Promise<any> {
        let attempt = 0;
        const maxRetries = 3;
        
        while (attempt < maxRetries) {
            try {
                await this.waitForRetryDelay(attempt);
                const method = (service as any)[methodName];
                const result = await method.call(service, data, parameters);
                
                if (result.success) {
                    return result;
                }
                
                attempt++;
            } catch (error) {
                await this.logRetryError(error, attempt);
                attempt++;
            }
        }
        
        throw new MaxRetriesExceededError(`Failed after ${maxRetries} attempts`);
    }
    
    private async getWorkflow(name: string): Promise<WorkflowDefinition> {
        return await fetchWorkflowDefinition(name);
    }
    
    private async evaluateCondition(condition: string, data: any): Promise<boolean> {
        return await evaluateConditionExpression(condition, data);
    }
    
    private async registerServiceCallbacks(name: string, service: AsyncService): Promise<void> {
        await service.onEvent('error', error => this.handleServiceError(name, error));
        await service.onEvent('warning', warning => this.handleServiceWarning(name, warning));
    }
    
    private async handleUnhealthyService(name: string, service: AsyncService): Promise<void> {
        await this.logServiceHealth(name, false);
        await this.attemptServiceRecovery(name, service);
    }
    
    private async processHealthCheckResults(results: PromiseSettledResult<any>[]): Promise<void> {
        for (const result of results) {
            if (result.status === 'rejected') {
                await this.handleHealthCheckFailure(result.reason);
            }
        }
    }
    
    private async waitForRetryDelay(attempt: number): Promise<void> {
        const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
        return new Promise(resolve => setTimeout(resolve, delay));
    }
    
    private async logRetryError(error: Error, attempt: number): Promise<void> {
        console.log(`Retry attempt ${attempt} failed:`, error);
    }
    
    private async handleServiceError(serviceName: string, error: Error): Promise<void> {
        await logServiceError(serviceName, error);
        await notifyServiceFailure(serviceName, error);
    }
    
    private async handleServiceWarning(serviceName: string, warning: string): Promise<void> {
        await logServiceWarning(serviceName, warning);
    }
    
    private async logServiceHealth(name: string, isHealthy: boolean): Promise<void> {
        console.log(`Service ${name} health: ${isHealthy ? 'OK' : 'FAILED'}`);
    }
    
    private async attemptServiceRecovery(name: string, service: AsyncService): Promise<void> {
        await service.restart();
        await service.initialize();
    }
    
    private async handleHealthCheckFailure(reason: any): Promise<void> {
        console.error('Health check failed:', reason);
    }
}

// Supporting function declarations for call graph testing
export async function fetchUser(userId: string): Promise<User> { return {} as User; }
export async function fetchUserPreferences(userId: string): Promise<UserPreferences> { return {} as UserPreferences; }
export async function fetchUserPermissions(userId: string): Promise<UserPermissions> { return {} as UserPermissions; }
export async function fetchUserOrders(userId: string): Promise<Order[]> { return []; }
export async function generateRecommendations(user: User, preferences: UserPreferences): Promise<Recommendation[]> { return []; }
export async function fetchNotifications(userId: string): Promise<Notification[]> { return []; }
export async function fetchPremiumData(userId: string): Promise<PremiumData> { return {} as PremiumData; }
export async function fetchAnalytics(userId: string): Promise<AnalyticsData> { return {} as AnalyticsData; }

export function buildPremiumProfile(...args: any[]): UserProfile { return {} as UserProfile; }
export function buildBasicProfile(...args: any[]): UserProfile { return {} as UserProfile; }

export async function validateInput(data: InputData): Promise<ValidatedData> { return {} as ValidatedData; }
export async function preprocessData(data: ValidatedData): Promise<PreprocessedData> { return {} as PreprocessedData; }
export async function transformData(data: PreprocessedData): Promise<TransformedData> { return {} as TransformedData; }
export async function enrichData(data: TransformedData): Promise<EnrichedData> { return {} as EnrichedData; }
export async function finalizeData(data: EnrichedData): Promise<ProcessedResult> { return {} as ProcessedResult; }
export async function handleProcessingError(error: Error): Promise<ProcessedResult> { return {} as ProcessedResult; }

export async function performStep1(operation: string): Promise<Step1Result> { return {} as Step1Result; }
export async function performStep2(step1: Step1Result): Promise<Step2Result> { return {} as Step2Result; }
export async function performStep3(step2: Step2Result): Promise<Step3Result> { return {} as Step3Result; }
export async function finalizeOperation(step3: Step3Result): Promise<OperationResult> { return {} as OperationResult; }

export async function logNetworkError(error: NetworkError): Promise<void> { }
export async function logValidationError(error: ValidationError): Promise<void> { }
export async function logUnknownError(error: Error): Promise<void> { }
export async function retryOperation(operation: string): Promise<OperationResult> { return {} as OperationResult; }
export async function handleValidationFailure(operation: string): Promise<OperationResult> { return {} as OperationResult; }

export function processDataAsync(data: CallbackData, callback: (error: Error | null, result?: any) => void): void { }
export function handleCallbackError(error: Error): void { }
export function transformResult(result: any, callback: (error: Error | null, result?: any) => void): void { }
export function handleTransformError(error: Error): void { }
export function finalizeResult(result: any, callback: (result: any) => void): void { }

export async function fetchItemsToProcess(): Promise<ProcessingItem[]> { return []; }
export async function processItemAsync(item: ProcessingItem): Promise<ProcessedItem> { return {} as ProcessedItem; }
export async function applySpecialProcessing(item: ProcessingItem): Promise<ProcessedItem> { return {} as ProcessedItem; }
export async function cleanupProcessing(): Promise<void> { }

export async function fetchFromSource(source: DataSource): Promise<SourceResult> { return {} as SourceResult; }
export async function fetchFromSourceWithRetry(source: DataSource): Promise<SourceResult> { return {} as SourceResult; }
export function processRaceWinner(result: SourceResult): FirstSuccessResult { return {} as FirstSuccessResult; }
export function processFallbackResults(results: SourceResult[]): FirstSuccessResult { return {} as FirstSuccessResult; }

export async function dynamicFetch(source: string): Promise<any> { return {}; }
export async function dynamicTransform(transformer: string, data: any[]): Promise<any> { return {}; }
export async function dynamicValidate(validator: string, data: any[]): Promise<boolean> { return true; }
export async function dynamicAggregate(aggregator: string, data: any[]): Promise<any> { return {}; }
export async function handleUnknownStepType(step: ProcessingStep): Promise<void> { }
export function combineDynamicResults(results: any[]): DynamicResult { return {} as DynamicResult; }

export async function createService(config: ServiceConfig): Promise<AsyncService> { return {} as AsyncService; }
export async function fetchWorkflowDefinition(name: string): Promise<WorkflowDefinition> { return {} as WorkflowDefinition; }
export async function evaluateConditionExpression(condition: string, data: any): Promise<boolean> { return true; }
export async function logServiceError(serviceName: string, error: Error): Promise<void> { }
export async function logServiceWarning(serviceName: string, warning: string): Promise<void> { }
export async function notifyServiceFailure(serviceName: string, error: Error): Promise<void> { }

// Type definitions for testing
interface User { id: string; isPremium: boolean; }
interface UserProfile { }
interface UserPreferences { }
interface UserPermissions { }
interface Order { }
interface Recommendation { }
interface Notification { }
interface PremiumData { }
interface AnalyticsData { }

interface InputData { }
interface ValidatedData { }
interface PreprocessedData { }
interface TransformedData { }
interface EnrichedData { }
interface ProcessedResult { }

interface Step1Result { }
interface Step2Result { }
interface Step3Result { }
interface OperationResult { }

interface CallbackData { }
interface ProcessingItem { requiresSpecialHandling: boolean; }
interface ProcessedItem { isValid: boolean; }

interface DataSource { }
interface SourceResult { }
interface FirstSuccessResult { }

interface DynamicConfig { processingSteps: ProcessingStep[]; }
interface ProcessingStep { 
    type: string; 
    name: string; 
    source?: string; 
    transformer?: string; 
    validator?: string; 
    aggregator?: string; 
}
interface DynamicResult { }

interface ServiceConfig { name: string; }
interface AsyncService {
    initialize(): Promise<void>;
    connect(): Promise<void>;
    healthCheck(): Promise<boolean>;
    restart(): Promise<void>;
    onEvent(event: string, handler: (data: any) => void): Promise<void>;
}

interface WorkflowDefinition {
    steps: WorkflowStep[];
}

interface WorkflowStep {
    serviceName: string;
    method: string;
    condition?: string;
    parameters: any;
    retryOnFailure: boolean;
}

// Error classes
class NetworkError extends Error { }
class ValidationError extends Error { }
class ProcessingError extends Error { }
class AllSourcesFailedError extends Error { }
class ServiceNotFoundError extends Error { }
class MethodNotFoundError extends Error { }
class MaxRetriesExceededError extends Error { }