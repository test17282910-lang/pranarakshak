'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface EmergencyContact {
  id: string;
  contact_name: string;
  relationship: string;
  phone: string | null;
  email: string | null;
  priority: number;
  notify_on_critical: boolean;
  notify_on_missed_checkin: boolean;
  active: boolean;
  created_at: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function EmergencyContactsPage() {
  const router = useRouter();
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingContact, setEditingContact] = useState<EmergencyContact | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    contact_name: '',
    relationship: 'spouse',
    phone: '',
    email: '',
    priority: 1,
    notify_on_critical: true,
    notify_on_missed_checkin: false,
  });

  useEffect(() => {
    const storedUserId = localStorage.getItem('userId');
    if (!storedUserId) {
      router.push('/login');
      return;
    }
    setUserId(storedUserId);
    fetchEmergencyContacts(storedUserId);
  }, [router]);

  const fetchEmergencyContacts = async (uid: string) => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/users/${uid}/emergency-contacts`);
      const data = await response.json();
      setContacts(data.emergency_contacts || []);
    } catch (error) {
      console.error('Error fetching emergency contacts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;

    try {
      const response = await fetch(`${BACKEND_URL}/emergency-contacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          ...formData,
          phone: formData.phone || null,
          email: formData.email || null,
        }),
      });

      if (response.ok) {
        setShowAddForm(false);
        resetForm();
        fetchEmergencyContacts(userId);
      }
    } catch (error) {
      console.error('Error adding emergency contact:', error);
    }
  };

  const handleUpdateContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId || !editingContact) return;

    try {
      const response = await fetch(`${BACKEND_URL}/emergency-contacts/${editingContact.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          ...formData,
          phone: formData.phone || null,
          email: formData.email || null,
        }),
      });

      if (response.ok) {
        setEditingContact(null);
        resetForm();
        fetchEmergencyContacts(userId);
      }
    } catch (error) {
      console.error('Error updating emergency contact:', error);
    }
  };

  const handleDeleteContact = async (contactId: string) => {
    if (!confirm('Are you sure you want to delete this emergency contact?')) return;

    try {
      const response = await fetch(`${BACKEND_URL}/emergency-contacts/${contactId}`, {
        method: 'DELETE',
      });

      if (response.ok && userId) {
        fetchEmergencyContacts(userId);
      }
    } catch (error) {
      console.error('Error deleting emergency contact:', error);
    }
  };

  const resetForm = () => {
    setFormData({
      contact_name: '',
      relationship: 'spouse',
      phone: '',
      email: '',
      priority: 1,
      notify_on_critical: true,
      notify_on_missed_checkin: false,
    });
  };

  const startEdit = (contact: EmergencyContact) => {
    setEditingContact(contact);
    setFormData({
      contact_name: contact.contact_name,
      relationship: contact.relationship,
      phone: contact.phone || '',
      email: contact.email || '',
      priority: contact.priority,
      notify_on_critical: contact.notify_on_critical,
      notify_on_missed_checkin: contact.notify_on_missed_checkin,
    });
    setShowAddForm(true);
  };

  const getRelationshipIcon = (relationship: string) => {
    const icons: Record<string, string> = {
      spouse: '💑',
      parent: '👴',
      child: '👶',
      sibling: '👫',
      friend: '🤝',
      doctor: '⚕️',
      caregiver: '👩‍⚕️',
    };
    return icons[relationship] || '👤';
  };

  const getPriorityBadge = (priority: number) => {
    const badges: Record<number, { color: string; label: string }> = {
      1: { color: 'bg-red-100 text-red-800', label: 'Highest' },
      2: { color: 'bg-orange-100 text-orange-800', label: 'High' },
      3: { color: 'bg-yellow-100 text-yellow-800', label: 'Medium' },
      4: { color: 'bg-blue-100 text-blue-800', label: 'Low' },
      5: { color: 'bg-gray-100 text-gray-800', label: 'Lowest' },
    };
    const badge = badges[priority] || badges[3];
    return <span className={`px-3 py-1 rounded-full text-xs font-semibold ${badge.color}`}>{badge.label}</span>;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-orange-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading emergency contacts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-orange-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              🚨 Emergency Contacts
            </h1>
            <p className="text-gray-600">
              Auto-notify loved ones during critical AQI events
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
              onClick={() => {
                setEditingContact(null);
                resetForm();
                setShowAddForm(true);
              }}
              className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition font-semibold"
            >
              + Add Emergency Contact
            </button>
          </div>
        </div>

        {/* Add/Edit Contact Form Modal */}
        {showAddForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-8">
              <h2 className="text-2xl font-bold mb-6">
                {editingContact ? 'Edit Emergency Contact' : 'Add Emergency Contact'}
              </h2>
              <form onSubmit={editingContact ? handleUpdateContact : handleAddContact} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Contact Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.contact_name}
                    onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                    placeholder="e.g., John Doe"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Relationship *
                  </label>
                  <select
                    value={formData.relationship}
                    onChange={(e) => setFormData({ ...formData, relationship: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                  >
                    <option value="spouse">Spouse/Partner</option>
                    <option value="parent">Parent</option>
                    <option value="child">Child</option>
                    <option value="sibling">Sibling</option>
                    <option value="friend">Friend</option>
                    <option value="doctor">Doctor</option>
                    <option value="caregiver">Caregiver</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                      placeholder="+919999999999"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                      placeholder="contact@example.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Priority Level (1 = Highest, 5 = Lowest)
                  </label>
                  <select
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                  >
                    <option value="1">1 - Highest Priority (Call First)</option>
                    <option value="2">2 - High Priority</option>
                    <option value="3">3 - Medium Priority</option>
                    <option value="4">4 - Low Priority</option>
                    <option value="5">5 - Lowest Priority</option>
                  </select>
                </div>

                <div className="space-y-3 border-t pt-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="notify_on_critical"
                      checked={formData.notify_on_critical}
                      onChange={(e) => setFormData({ ...formData, notify_on_critical: e.target.checked })}
                      className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
                    />
                    <label htmlFor="notify_on_critical" className="text-sm text-gray-700">
                      🚨 Send emergency alert during CRITICAL AQI events (Recommended)
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="notify_on_missed_checkin"
                      checked={formData.notify_on_missed_checkin}
                      onChange={(e) => setFormData({ ...formData, notify_on_missed_checkin: e.target.checked })}
                      className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
                    />
                    <label htmlFor="notify_on_missed_checkin" className="text-sm text-gray-700">
                      Notify if I don't check the app during high AQI
                    </label>
                  </div>
                </div>

                <p className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
                  Note: At least one contact method (phone or email) is required for notifications to work.
                </p>

                <div className="flex gap-4 mt-6">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddForm(false);
                      setEditingContact(null);
                      resetForm();
                    }}
                    className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition font-semibold"
                  >
                    {editingContact ? 'Update Contact' : 'Add Contact'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Emergency Contacts List */}
        {contacts.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
            <div className="text-6xl mb-4">🚨</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">No Emergency Contacts Yet</h3>
            <p className="text-gray-600 mb-6">
              Add emergency contacts to be automatically notified during critical AQI events
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg transition font-semibold"
            >
              Add Your First Emergency Contact
            </button>
          </div>
        ) : (
          <div className="grid gap-6">
            {contacts.map((contact) => (
              <div
                key={contact.id}
                className="bg-white rounded-2xl shadow-lg p-6 hover:shadow-xl transition border-l-4 border-red-500"
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-red-400 to-orange-400 rounded-full flex items-center justify-center text-3xl">
                      {getRelationshipIcon(contact.relationship)}
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold text-gray-900">{contact.contact_name}</h3>
                      <p className="text-gray-600 capitalize">{contact.relationship.replace('_', ' ')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {getPriorityBadge(contact.priority)}
                    <button
                      onClick={() => startEdit(contact)}
                      className="text-blue-500 hover:text-blue-700 transition"
                      title="Edit contact"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => handleDeleteContact(contact.id)}
                      className="text-red-500 hover:text-red-700 transition"
                      title="Delete contact"
                    >
                      🗑️
                    </button>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {contact.phone && (
                    <div className="flex items-center gap-2 text-gray-700">
                      <span>📱 Phone:</span>
                      <span className="font-medium">{contact.phone}</span>
                    </div>
                  )}
                  
                  {contact.email && (
                    <div className="flex items-center gap-2 text-gray-700">
                      <span>📧 Email:</span>
                      <span className="font-medium">{contact.email}</span>
                    </div>
                  )}

                  <div className="flex items-center gap-4 mt-4 text-sm">
                    {contact.notify_on_critical && (
                      <span className="text-red-600 font-medium">
                        🚨 Critical Alert: ON
                      </span>
                    )}
                    {contact.notify_on_missed_checkin && (
                      <span className="text-orange-600">
                        ⏰ Missed Check-in: ON
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-xs text-gray-500">
                    Added on {new Date(contact.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Box */}
        <div className="mt-8 bg-red-50 border border-red-200 rounded-2xl p-6">
          <h3 className="font-bold text-red-900 mb-2">🚨 How Emergency Alerts Work</h3>
          <ul className="space-y-2 text-sm text-red-800">
            <li>• When your AQI reaches CRITICAL levels, emergency contacts are automatically notified via WhatsApp AND Email</li>
            <li>• Contacts are notified in priority order (1 = first, 5 = last)</li>
            <li>• Notifications include your current health status, location, and immediate action steps</li>
            <li>• No cooldown period for emergency alerts - every critical event triggers notifications</li>
            <li>• All emergency alerts are logged for your medical records</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
