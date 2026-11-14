import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { InstructorApp } from './instructor/InstructorApp';
import { ProjectionView } from './projection/ProjectionView';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/projection" element={<ProjectionView />} />
        <Route path="/*" element={<InstructorApp />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
