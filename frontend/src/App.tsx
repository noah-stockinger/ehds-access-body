import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Apply from './pages/Apply'
import ApplicantView from './pages/ApplicantView'
import Spe from './pages/Spe'
import Staff from './pages/Staff'
import { DemoBar, Footer } from './ui'

export default function App() {
  return (
    <BrowserRouter>
      <DemoBar />
      <Routes>
        <Route path="/" element={<Navigate to="/staff" replace />} />
        <Route path="/apply" element={<Apply />} />
        <Route path="/applicant/:id" element={<ApplicantView />} />
        <Route path="/staff" element={<Staff />} />
        <Route path="/staff/:id" element={<Staff />} />
        <Route path="/spe/:id" element={<Spe />} />
        <Route path="*" element={<main className="wrap"><p>Page not found.</p></main>} />
      </Routes>
      <Footer />
    </BrowserRouter>
  )
}
