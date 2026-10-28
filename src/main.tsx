import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ModalProvider } from './context/ModalContext';
import { CmsProvider } from './context/CmsContext';
import App from './App';
import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <CmsProvider>
        <ModalProvider>
          <App />
        </ModalProvider>
      </CmsProvider>
    </BrowserRouter>
  </React.StrictMode>
);
