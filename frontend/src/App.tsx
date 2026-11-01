import { Route, Routes } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { AlertsPage } from './pages/Alerts'
import { DashboardPage } from './pages/Dashboard'
import { DeviceDetailPage } from './pages/DeviceDetail'
import { DevicesPage } from './pages/Devices'
import { LoginPage } from './pages/Login'
import { MapPage } from './pages/Map'
import { NewDevicePage } from './pages/NewDevice'
import { NotFoundPage } from './pages/NotFound'
import { ResultsPage } from './pages/Results'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="devices/new" element={<NewDevicePage />} />
        <Route path="devices/:id" element={<DeviceDetailPage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
