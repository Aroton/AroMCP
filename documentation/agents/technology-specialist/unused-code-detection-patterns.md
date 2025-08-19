# Unused Code Detection Patterns for TypeScript/JavaScript Projects

**Research Date**: July 31, 2025
**Sources**: ESLint, TypeScript-ESLint, Meta Engineering, Effective TypeScript, Knip, Webpack, Rollup
**Key Findings**: Multiple complementary approaches needed for comprehensive dead code detection

## Problem Context

Detecting unused code in modern TypeScript/JavaScript projects presents significant challenges due to:
- Framework-specific entry points (Next.js pages, API routes)
- Dynamic imports and string-based references
- Reflection and computed property access
- Complex build system configurations
- Monorepo dependencies and shared code

## 1. Tool Categories and Approaches

### Static Analysis Tools

#### TypeScript Compiler Built-in Options
```json
{
  "compilerOptions": {
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

**Limitations**:
- Only detects local variables and parameters
- Cannot configure patterns or exceptions
- Too aggressive for development workflows

#### ESLint with TypeScript-ESLint
```javascript
{
  "rules": {
    "no-unused-vars": "off",
    "@typescript-eslint/no-unused-vars": [
      "error",
      {
        "varsIgnorePattern": "^_",
        "argsIgnorePattern": "^_",
        "ignoreRestSiblings": true
      }
    ]
  }
}
```

**Advantages**:
- Highly configurable with ignore patterns
- Line-level and file-level configuration
- Integrates with CI/CD pipelines
- Handles TypeScript-specific features

### Specialized Dead Code Detection Tools

#### ts-prune
Zero-config CLI tool using "mark and sweep" analysis:

```json
// tsconfig.ts-prune.json
{
  "extends": "./tsconfig.json",
  "include": [
    "src/index.ts",
    "src/cli.ts",
    "pages/**/*.ts",
    "api/**/*.ts"
  ]
}
```

**Algorithm**:
1. Traces references from specified entry points
2. Marks all reachable symbols as "live"
3. Reports unmarked exports as unused
4. Handles mutual recursion and complex dependencies

#### Knip (2024 Recommended)
Modern tool with 100+ framework plugins:

```javascript
// knip.config.js
export default {
  entry: ['src/index.ts', 'pages/**/*.tsx'],
  project: ['src/**/*.ts', 'pages/**/*.tsx'],
  ignore: ['**/*.test.ts', '**/*.stories.ts'],
  ignoreDependencies: ['@types/*']
}
```

**Key Features**:
- Framework-aware analysis (Next.js, React, Vite, etc.)
- Detects unused files, exports, and dependencies
- Monorepo support
- Symbol-level granularity
- Automated CI/CD integration

### Bundle-Level Dead Code Elimination

#### Webpack Tree Shaking
```javascript
// webpack.config.js
module.exports = {
  mode: 'production',
  optimization: {
    usedExports: true,
    sideEffects: false
  }
}
```

#### Rollup Tree Shaking
Native ES module support with automatic dead code elimination.

#### esbuild
High-performance bundler with built-in tree shaking.

## 2. Framework-Specific Challenges and Solutions

### Next.js Patterns

**Challenge**: File-based routing creates false positives
```
pages/
├── index.tsx      # Auto-imported by Next.js
├── api/users.ts   # API endpoint, not imported
└── _app.tsx       # Framework entry point
```

**Solutions**:
1. Configure entry points in detection tools:
```javascript
// knip.config.js for Next.js
export default {
  entry: [
    'pages/**/*.{js,ts,jsx,tsx}',
    'pages/api/**/*.{js,ts}',
    'src/pages/**/*.{js,ts,jsx,tsx}'
  ],
  nextjs: {
    entry: ['next.config.js']
  }
}
```

2. Use Next.js-specific plugins that understand routing conventions

### Dynamic Imports

**Challenge**: String-based imports not detected by static analysis
```typescript
// These patterns are problematic for static analysis
const componentName = 'UserProfile';
const Component = await import(`./components/${componentName}`);

// Route-based dynamic imports
const page = await import(`./pages/${router.pathname}`);
```

**Solutions**:
1. Use explicit dynamic import mapping:
```typescript
// Create explicit mapping for static analysis
const COMPONENT_MAP = {
  UserProfile: () => import('./components/UserProfile'),
  AdminPanel: () => import('./components/AdminPanel')
};
```

2. Configure ignore patterns for legitimate dynamic import directories

### React Component Detection

**Challenge**: Components referenced through JSX, HOCs, or computed properties
```typescript
// Static analysis challenges
const components = { UserCard, ProductCard };
const ComponentType = components[type]; // Computed property

// HOC patterns
const EnhancedComponent = withAuth(UserProfile);

// String-based component references
const componentName = 'UserProfile';
React.createElement(componentName);
```

**Solutions**:
1. Use React-specific ESLint plugins:
```javascript
{
  "plugins": ["react-unused"],
  "rules": {
    "react-unused/unused-component": "error"
  }
}
```

2. Maintain explicit component registries for dynamic usage

## 3. Advanced Algorithms and Techniques

### Meta's SCARF Framework Architecture

**Multi-layered Analysis**:
1. **Static Dependency Graph**: Extract symbol-level dependencies
2. **Dynamic Usage Tracking**: Runtime usage from logs and telemetry
3. **Graph Analysis**: Identify unreachable nodes and cycles
4. **Safety Validation**: Domain-specific rules to prevent false positives

**Key Innovations**:
- Symbol-level rather than file-level analysis
- Cycle detection and removal
- 50% improvement in dead code detection accuracy
- Automated change generation with human-readable explanations

### Dependency Graph Analysis

```typescript
interface DependencyNode {
  symbol: string;
  dependencies: Set<string>;
  referencedBy: Set<string>;
  isExported: boolean;
  isEntry: boolean;
}

class DeadCodeAnalyzer {
  private buildDependencyGraph(): Map<string, DependencyNode> {
    // Extract all symbols and their relationships
  }
  
  private markLiveSymbols(entryPoints: string[]): Set<string> {
    const live = new Set<string>();
    const queue = [...entryPoints];
    
    while (queue.length > 0) {
      const current = queue.pop()!;
      if (live.has(current)) continue;
      
      live.add(current);
      const node = this.graph.get(current);
      if (node) {
        queue.push(...node.dependencies);
      }
    }
    
    return live;
  }
}
```

## 4. Performance Considerations for Large Codebases

### Incremental Analysis
```typescript
interface AnalysisCache {
  fileHashes: Map<string, string>;
  symbolDependencies: Map<string, Set<string>>;
  lastAnalysisTime: number;
}

class IncrementalAnalyzer {
  async analyzeChangedFiles(changedFiles: string[]): Promise<AnalysisResult> {
    // Only reanalyze affected portions of dependency graph
    const affectedSymbols = this.getAffectedSymbols(changedFiles);
    return this.analyzeSymbols(affectedSymbols);
  }
}
```

### Memory-Efficient Graph Processing
- Stream processing for large dependency graphs
- Lazy loading of symbol information
- Chunked analysis for monorepos
- Parallel processing of independent modules

### Build Integration Strategies
```javascript
// webpack plugin approach
class UnusedCodePlugin {
  apply(compiler) {
    compiler.hooks.afterCompile.tap('UnusedCodePlugin', (compilation) => {
      const usedModules = new Set(compilation.modules.map(m => m.resource));
      const allModules = this.getAllProjectModules();
      const unused = allModules.filter(m => !usedModules.has(m));
      // Report unused modules
    });
  }
}
```

## 5. False Positive Minimization Strategies

### Configuration-Based Exclusions
```javascript
// knip.config.js
export default {
  // Exclude test files and their dependencies
  ignore: [
    '**/*.test.{js,ts,tsx}',
    '**/*.spec.{js,ts,tsx}',
    '**/__tests__/**',
    '**/test-utils/**'
  ],
  
  // Exclude development and build-time dependencies
  ignoreDependencies: [
    '@types/*',
    'eslint-*',
    'jest-*',
    'webpack-*'
  ],
  
  // Framework-specific exclusions
  entry: [
    'src/index.ts',
    'pages/**/*.{js,ts,jsx,tsx}', // Next.js pages
    'src/pages/**/*.{js,ts,jsx,tsx}' // Alternative structure
  ]
}
```

### Pattern-Based Safe Lists
```typescript
interface SafeListConfig {
  // Patterns for legitimately unused exports
  exportPatterns: string[];
  // Files that should be ignored entirely
  filePatterns: string[];
  // Dependency patterns to ignore
  dependencyPatterns: string[];
}

const safeListConfig: SafeListConfig = {
  exportPatterns: [
    '*.d.ts', // Type definition files
    'index.ts', // Re-export files
    'config/*' // Configuration files
  ],
  filePatterns: [
    '**/*.stories.{js,ts,tsx}', // Storybook files
    '**/*.test.{js,ts,tsx}', // Test files
    '**/scripts/**' // Build scripts
  ],
  dependencyPatterns: [
    '@types/*', // Type definitions
    '*-webpack-plugin', // Build tools
    'eslint-*' // Linting tools
  ]
};
```

### Multi-Analysis Validation
```typescript
class ValidationPipeline {
  async validateUnusedCode(candidates: string[]): Promise<string[]> {
    const results = await Promise.all([
      this.staticAnalysis(candidates),
      this.dynamicAnalysis(candidates),
      this.testCoverageAnalysis(candidates)
    ]);
    
    // Only report items flagged by multiple analyses
    return this.intersectResults(results);
  }
}
```

## 6. Implementation Recommendations

### Tier 1: Essential Setup
1. **ESLint with TypeScript-ESLint**: Basic unused variable detection
2. **Knip**: Modern framework-aware dead code detection
3. **Bundle analyzer**: Tree shaking validation

### Tier 2: Advanced Analysis
1. **Custom static analysis**: Project-specific patterns
2. **Dynamic analysis integration**: Runtime usage tracking
3. **CI/CD automation**: Continuous dead code prevention

### Tier 3: Enterprise Scale
1. **Incremental analysis**: Performance optimization
2. **Cross-repository analysis**: Monorepo-wide detection
3. **Automated cleanup**: Safe code removal with validation

## 7. Best Practices

### Development Workflow
```bash
# Regular cleanup cycle
npm run knip              # Detect unused code
npm run test              # Ensure tests pass
npm run build             # Verify build succeeds
git add . && git commit   # Commit cleanup
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Detect unused code
  run: |
    npm run knip
    if [ $? -ne 0 ]; then
      echo "Unused code detected. Please clean up before merging."
      exit 1
    fi
```

### Progressive Adoption
1. Start with ESLint unused variable rules
2. Add Knip for file and export detection
3. Configure framework-specific patterns
4. Implement automated cleanup pipelines
5. Add dynamic analysis for high-confidence scenarios

## Trade-offs Analysis

| Approach | Accuracy | Performance | Setup Complexity | Framework Support |
|----------|----------|-------------|------------------|-------------------|
| ESLint | Medium | High | Low | Medium |
| ts-prune | High | Medium | Medium | Low |
| Knip | High | High | Low | High |
| Bundle Analysis | Medium | Low | High | High |
| Custom Static | Very High | Medium | Very High | Custom |
| Dynamic Analysis | Very High | Low | High | Medium |

## Conclusion

Effective unused code detection requires a multi-layered approach combining static analysis tools like Knip with framework-specific configurations and CI/CD integration. The key is balancing accuracy with performance while minimizing false positives through careful configuration and validation strategies.

For most TypeScript/JavaScript projects in 2024, the recommended approach is:
1. Knip for comprehensive dead code detection
2. TypeScript-ESLint for unused variables
3. Framework-specific entry point configuration
4. Automated CI/CD validation
5. Regular cleanup cycles with validation