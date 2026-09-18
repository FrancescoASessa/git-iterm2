import js from '@eslint/js'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: {
        window: 'readonly',
        document: 'readonly',
        location: 'readonly',
        history: 'readonly',
        fetch: 'readonly',
        WebSocket: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        console: 'readonly',
      },
    },
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'error',
      'no-restricted-properties': [
        'error',
        {
          object: 'window',
          property: 'localStorage',
          message: 'The panel never persists anything locally.',
        },
        {
          object: 'globalThis',
          property: 'localStorage',
          message: 'The panel never persists anything locally.',
        },
      ],
      'no-restricted-syntax': [
        'error',
        {
          selector: "Identifier[name='localStorage']",
          message: 'The panel never persists anything locally.',
        },
      ],
    },
  },
  { ignores: ['dist', 'src/api/types.gen.ts'] },
)
