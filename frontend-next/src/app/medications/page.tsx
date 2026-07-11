'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface Medication {
  id: string;
  medication_name: string;
  medication_type: string;
  dosage: string;
  frequency: string;
  custom_schedule: string[];
  aqi_trigger: number | null;
  condition_specific: boolean;
  active: boolean;
  created_at: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function MedicationsPage() {
  const router = useRouter();
  const [medications, setMedications] = useState<Medication[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  
  // Form state
  const [formData, setFormData] = useState({
    medication_name: '',
    medication_type: 'rescue_inhaler',
    dosage: '',
    frequency: 'as_needed',
    custom_schedule: [] as string[],
    aqi_trigger: 100,
    condition_specific: true,
  });

  useEffect(() => {
    // Get user ID from localStorage
    const storedUserId = localStorage.getItem('userId');
    if (!storedUserId) {
      router.push('/login');
      return;
    }
    setUserId(storedUserId);
    fetchMedications(storedUserId);
  }, [router]);

  const fetchMedications = async (uid: string) => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/users/${uid}/medications`);
      const data = await response.json();
      setMedications(data.medications || []);
    } catch (error) {
      console.error('Error fetching medications:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddMedication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;

    try {
      const response = await fetch(`${BACKEND_URL}/medications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          ...formData,
        }),
      });

      if (response.ok) {
        setShowAddForm(false);
        setFormData({
          medication_name: '',
          medication_type: 'rescue_inhaler',
          dosage: '',
          frequency: 'as_needed',
          custom_schedule: [],
          aqi_trigger: 100,
          condition_specific: true,
        });
        fetchMedications(userId);
      }
    } catch (error) {
      console.error('Error adding medication:', error);
    }
  };

  const handleDeleteMedication = async (medicationId: string) => {
    if (!confirm('Are you sure you want to delete this medication?')) return;

    try {
      const response = await fetch(`${BACKEND_URL}/medications/${medicationId}`, {
        method: 'DELETE',
      });

      if (response.ok && userId) {
        fetchMedications(userId);
      }
    } catch (error) {
      console.error('Error deleting medication:', error);
    }
  };

  const getMedicationTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      rescue_inhaler: '💨',
      preventer_inhaler: '🌬️',
      nebulizer: '🫁',
      oral: '💊',
      other: '💉',
    };
    return icons[type] || '💊';
  };

  const getFrequencyLabel = (frequency: string) => {
    const labels: Record<string, string> = {
      as_needed: 'As Needed',
      daily: 'Once Daily',
      twice_daily: 'Twice Daily',
      thrice_daily: 'Three Times Daily',
      custom: 'Custom Schedule',
    };
    return labels[frequency] || frequency;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading medications...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              💊 My Medications
            </h1>
            <p className="text-gray-600">
              Manage your medications with AQI-based reminders
            </p>
          </div>
          <div className="flex gap-4">
            <button
              onClick={() => router.push('/dashboard')}
              className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition"
            >
              ← Back to Dashboard
            </button>
            <button
              onClick={() => setShowAddForm(true)}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-semibold"
            >
              + Add Medication
            </button>
          </div>
        </div>

        {/* Add Medication Form Modal */}
        {showAddForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-8">
              <h2 className="text-2xl font-bold mb-6">Add New Medication</h2>
              <form onSubmit={handleAddMedication} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Medication Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.medication_name}
                    onChange={(e) => setFormData({ ...formData, medication_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., Salbutamol Inhaler"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Medication Type *
                  </label>
                  <select
                    value={formData.medication_type}
                    onChange={(e) => setFormData({ ...formData, medication_type: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="rescue_inhaler">Rescue Inhaler</option>
                    <option value="preventer_inhaler">Preventer Inhaler</option>
                    <option value="nebulizer">Nebulizer</option>
                    <option value="oral">Oral Medication</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Dosage *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.dosage}
                    onChange={(e) => setFormData({ ...formData, dosage: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., 2 puffs every 4-6 hours"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Frequency *
                  </label>
                  <select
                    value={formData.frequency}
                    onChange={(e) => setFormData({ ...formData, frequency: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="as_needed">As Needed</option>
                    <option value="daily">Once Daily</option>
                    <option value="twice_daily">Twice Daily</option>
                    <option value="thrice_daily">Three Times Daily</option>
                    <option value="custom">Custom Schedule</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    AQI Trigger Threshold
                  </label>
                  <input
                    type="number"
                    value={formData.aqi_trigger || ''}
                    onChange={(e) => setFormData({ ...formData, aqi_trigger: parseInt(e.target.value) || 100 })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="100"
                    min="50"
                    max="500"
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    You'll receive a reminder when AQI crosses this threshold
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="condition_specific"
                    checked={formData.condition_specific}
                    onChange={(e) => setFormData({ ...formData, condition_specific: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="condition_specific" className="text-sm text-gray-700">
                    Adjust reminders based on my condition severity
                  </label>
                </div>

                <div className="flex gap-4 mt-6">
                  <button
                    type="button"
                    onClick={() => setShowAddForm(false)}
                    className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-semibold"
                  >
                    Add Medication
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Medications List */}
        {medications.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
            <div className="text-6xl mb-4">💊</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">No Medications Yet</h3>
            <p className="text-gray-600 mb-6">
              Add your medications to receive AQI-based reminders
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-semibold"
            >
              Add Your First Medication
            </button>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            {medications.map((med) => (
              <div
                key={med.id}
                className="bg-white rounded-2xl shadow-lg p-6 hover:shadow-xl transition border-l-4 border-blue-500"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center gap-3">
                    <div className="text-4xl">{getMedicationTypeIcon(med.medication_type)}</div>
                    <div>
                      <h3 className="text-xl font-bold text-gray-900">{med.medication_name}</h3>
                      <p className="text-sm text-gray-500 capitalize">
                        {med.medication_type.replace('_', ' ')}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteMedication(med.id)}
                    className="text-red-500 hover:text-red-700 transition"
                    title="Delete medication"
                  >
                    🗑️
                  </button>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-600">💉 Dosage:</span>
                    <span className="font-medium">{med.dosage}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-gray-600">📅 Frequency:</span>
                    <span className="font-medium">{getFrequencyLabel(med.frequency)}</span>
                  </div>

                  {med.aqi_trigger && (
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600">🚨 AQI Trigger:</span>
                      <span className="font-medium bg-orange-100 text-orange-800 px-3 py-1 rounded-full text-sm">
                        {med.aqi_trigger}+
                      </span>
                    </div>
                  )}

                  {med.condition_specific && (
                    <div className="flex items-center gap-2 text-sm text-blue-600">
                      <span>✓</span>
                      <span>Personalized for your condition</span>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-xs text-gray-500">
                    Added on {new Date(med.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Box */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-2xl p-6">
          <h3 className="font-bold text-blue-900 mb-2">💡 How Medication Reminders Work</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li>• When AQI crosses your medication's trigger threshold, you'll receive an automatic WhatsApp reminder</li>
            <li>• Reminders have a 6-hour cooldown to prevent notification spam</li>
            <li>• Personalized reminders adapt to your condition severity and current symptoms</li>
            <li>• All reminders are logged in the system for your health records</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
