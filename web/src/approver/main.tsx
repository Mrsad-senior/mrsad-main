import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../shared/styles/tokens.css';
import '../shared/styles/base.css';
import '../shared/styles/components.css';
import './approver.css';
import { missingEnv } from '../shared/app/config';
import { ConfigError } from '../shared/components/ConfigError';
import { I18nProvider } from '../shared/i18n';
import { ApproverApp } from './App';

const root = document.getElementById('root');
const missing = missingEnv();
if (root) {
  createRoot(root).render(
    <StrictMode>
      {missing.length > 0 ? (
        <I18nProvider>
          <ConfigError missing={missing} />
        </I18nProvider>
      ) : (
        <ApproverApp />
      )}
    </StrictMode>,
  );
}
