import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LegalNotice from './components/LegalNotice';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import HomePage from './pages/index';
import CheckerPage from './pages/checker';
import LegalPage from './pages/legal';

const App = () => (
  <Router>
    <div className="min-h-screen flex flex-col">
      <LegalNotice />
      <Navbar />
      <main className="flex-grow p-4">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/check" element={<CheckerPage />} />
          <Route path="/legal" element={<LegalPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  </Router>
);

export default App;
