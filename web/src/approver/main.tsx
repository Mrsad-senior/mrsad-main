import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../shared/styles/tokens.css';
import '../shared/styles/base.css';
import '../shared/styles/components.css';
import './approver.css';
import { ApproverApp } from './App';

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <StrictMode>
      <ApproverApp />
    </StrictMode>,
  );
}
