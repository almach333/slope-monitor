/**
 * Metadata for every sensor field: label, unit and decimals.
 * Cards, charts, tables, the Results dropdown and the rules editor all read
 * from here, so a unit or label only needs changing in one place.
 */

export interface FieldMeta {
  label: string
  unit: string
  decimals: number
}

export const FIELDS: Record<string, FieldMeta> = {
  // Derived (computed by the backend)
  tilt_change_total: { label: 'Tilt change', unit: '°', decimals: 3 },
  tilt_change_x: { label: 'Tilt change X', unit: '°', decimals: 3 },
  tilt_change_y: { label: 'Tilt change Y', unit: '°', decimals: 3 },
  slope_angle: { label: 'Slope angle', unit: '°', decimals: 2 },
  acc_magnitude: { label: 'Acceleration', unit: 'g', decimals: 3 },
  gyro_magnitude: { label: 'Gyroscope', unit: '°/s', decimals: 3 },
  mag_magnitude: { label: 'Magnetic field', unit: 'µT', decimals: 1 },
  displacement_m: { label: 'Movement', unit: 'm', decimals: 2 },
  // Raw
  angle_x: { label: 'Angle X', unit: '°', decimals: 2 },
  angle_y: { label: 'Angle Y', unit: '°', decimals: 2 },
  angle_z: { label: 'Heading', unit: '°', decimals: 1 },
  acc_x: { label: 'Acc X', unit: 'g', decimals: 4 },
  acc_y: { label: 'Acc Y', unit: 'g', decimals: 4 },
  acc_z: { label: 'Acc Z', unit: 'g', decimals: 4 },
  gyro_x: { label: 'Gyro X', unit: '°/s', decimals: 3 },
  gyro_y: { label: 'Gyro Y', unit: '°/s', decimals: 3 },
  gyro_z: { label: 'Gyro Z', unit: '°/s', decimals: 3 },
  mag_x: { label: 'Mag X', unit: 'µT', decimals: 1 },
  mag_y: { label: 'Mag Y', unit: 'µT', decimals: 1 },
  mag_z: { label: 'Mag Z', unit: 'µT', decimals: 1 },
  temperature: { label: 'Temperature', unit: '°C', decimals: 1 },
  humidity: { label: 'Humidity', unit: '%RH', decimals: 1 },
  battery_pct: { label: 'Battery', unit: '%', decimals: 1 },
  battery_v: { label: 'Battery voltage', unit: 'V', decimals: 2 },
  rssi: { label: 'RSSI', unit: 'dBm', decimals: 0 },
  snr: { label: 'SNR', unit: 'dB', decimals: 1 },
  lat: { label: 'Latitude', unit: '', decimals: 6 },
  lon: { label: 'Longitude', unit: '', decimals: 6 },
}

/** The 9 parameters required by the user stories (shown on every device card). */
export const NINE_PARAMETERS = [
  'tilt_change_total',
  'slope_angle',
  'acc_magnitude',
  'gyro_magnitude',
  'mag_magnitude',
  'temperature',
  'humidity',
  'battery_pct',
  'displacement_m',
]

/** Parameters an alert rule can watch (must match backend alert_defaults.py). */
export const ALERT_PARAMETERS = [
  'tilt_change_total',
  'slope_angle',
  'acc_magnitude',
  'battery_pct',
  'displacement_m',
  'temperature',
  'humidity',
  'gyro_magnitude',
  'mag_magnitude',
]

export interface ChartGroup {
  title: string
  fields: string[]
  /** Fields drawn against a second (right-hand) axis. */
  rightFields?: string[]
  /** Alert-rule parameter whose thresholds are drawn on this chart. */
  ruleParameter?: string
  note?: string
}

/** Device detail: one chart per parameter group. */
export const CHART_GROUPS: ChartGroup[] = [
  { title: 'Tilt change', fields: ['tilt_change_x', 'tilt_change_y', 'tilt_change_total'], ruleParameter: 'tilt_change_total', note: 'since baseline' },
  { title: 'Slope angle', fields: ['angle_x', 'angle_y', 'slope_angle'], ruleParameter: 'slope_angle' },
  { title: 'Acceleration', fields: ['acc_x', 'acc_y', 'acc_z', 'acc_magnitude'], ruleParameter: 'acc_magnitude' },
  { title: 'Gyroscope', fields: ['gyro_x', 'gyro_y', 'gyro_z'], ruleParameter: 'gyro_magnitude' },
  { title: 'Magnetic field', fields: ['mag_x', 'mag_y', 'mag_z', 'mag_magnitude'], ruleParameter: 'mag_magnitude' },
  { title: 'Temperature', fields: ['temperature'], ruleParameter: 'temperature' },
  { title: 'Humidity', fields: ['humidity'], ruleParameter: 'humidity' },
  { title: 'Battery', fields: ['battery_pct'], ruleParameter: 'battery_pct' },
  { title: 'Movement', fields: ['displacement_m'], ruleParameter: 'displacement_m', note: 'GPS, coarse (± a few m)' },
  { title: 'Link quality', fields: ['rssi'], rightFields: ['snr'] },
]

/** Fields offered on the Results page. */
export const RESULT_FIELDS = [...NINE_PARAMETERS, 'angle_x', 'angle_y', 'battery_v', 'rssi', 'snr']

export function fieldLabel(field: string): string {
  return FIELDS[field]?.label ?? field
}

export function fieldUnit(field: string): string {
  return FIELDS[field]?.unit ?? ''
}

/** Colours for lines within one chart (x, y, z, total). Not the status colours. */
export const SERIES_COLOURS = ['#38bdf8', '#c084fc', '#f472b6', '#e2e8f0']

/** Colours for one line per node (Dashboard strip, Results). */
export const NODE_COLOURS = ['#38bdf8', '#c084fc', '#f472b6', '#2dd4bf', '#e2e8f0', '#818cf8', '#fda4af', '#a3e635']
