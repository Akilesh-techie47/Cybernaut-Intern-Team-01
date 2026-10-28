import { Routes, Route } from 'react-router-dom';
import { ToastProvider } from './hooks/useToast.jsx';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import SearchPage from './pages/SearchPage';
import ProductDetail from './pages/ProductDetail';
import HistoryPage from './pages/HistoryPage';

function App() {
  return (
    <ToastProvider>
      <MainLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/product/:id" element={<ProductDetail />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </MainLayout>
    </ToastProvider>
  );
}

export default App;