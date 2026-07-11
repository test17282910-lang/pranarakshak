'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface FamilyGroup {
  id: string;
  group_name: string;
  description: string;
  creator_user_id: string;
  shared_alert_threshold: number;
  auto_share_location: boolean;
  emergency_mode: boolean;
  user_role: string;
  notifications_enabled: boolean;
  created_at: string;
}

interface FamilyMember {
  id: string;
  name: string;
  email: string;
  phone: string;
  condition: string;
  severity: string;
  role: string;
  notifications_enabled: boolean;
  joined_at: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function FamilyGroupsPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<FamilyGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [groupMembers, setGroupMembers] = useState<FamilyMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    group_name: '',
    description: '',
    shared_alert_threshold: 100,
    auto_share_location: true,
    emergency_mode: true,
  });

  useEffect(() => {
    const storedUserId = localStorage.getItem('userId');
    if (!storedUserId) {
      router.push('/login');
      return;
    }
    setUserId(storedUserId);
    fetchFamilyGroups(storedUserId);
  }, [router]);

  const fetchFamilyGroups = async (uid: string) => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/users/${uid}/family-groups`);
      const data = await response.json();
      setGroups(data.family_groups || []);
    } catch (error) {
      console.error('Error fetching family groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchGroupMembers = async (groupId: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/family-groups/${groupId}/members`);
      const data = await response.json();
      setGroupMembers(data.members || []);
    } catch (error) {
      console.error('Error fetching group members:', error);
    }
  };

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;

    try {
      const response = await fetch(`${BACKEND_URL}/family-groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          creator_user_id: userId,
        }),
      });

      if (response.ok) {
        setShowCreateForm(false);
        setFormData({
          group_name: '',
          description: '',
          shared_alert_threshold: 100,
          auto_share_location: true,
          emergency_mode: true,
        });
        fetchFamilyGroups(userId);
      }
    } catch (error) {
      console.error('Error creating family group:', error);
    }
  };

  const handleSelectGroup = (groupId: string) => {
    setSelectedGroup(groupId);
    fetchGroupMembers(groupId);
  };

  const getRoleIcon = (role: string) => {
    const icons: Record<string, string> = {
      admin: '👑',
      member: '👤',
      guardian: '🛡️',
    };
    return icons[role] || '👤';
  };

  const getRoleBadgeColor = (role: string) => {
    const colors: Record<string, string> = {
      admin: 'bg-purple-100 text-purple-800',
      member: 'bg-blue-100 text-blue-800',
      guardian: 'bg-green-100 text-green-800',
    };
    return colors[role] || 'bg-gray-100 text-gray-800';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-pink-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading family groups...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-pink-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              👨‍👩‍👧‍👦 Family Groups
            </h1>
            <p className="text-gray-600">
              Stay connected with your loved ones during high AQI events
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
              onClick={() => setShowCreateForm(true)}
              className="px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition font-semibold"
            >
              + Create Family Group
            </button>
          </div>
        </div>

        {/* Create Group Form Modal */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-8">
              <h2 className="text-2xl font-bold mb-6">Create Family Group</h2>
              <form onSubmit={handleCreateGroup} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Group Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.group_name}
                    onChange={(e) => setFormData({ ...formData, group_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                    placeholder="e.g., My Family, Parents Group"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                    placeholder="What's this group for?"
                    rows={3}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Shared Alert Threshold (AQI)
                  </label>
                  <input
                    type="number"
                    value={formData.shared_alert_threshold}
                    onChange={(e) => setFormData({ ...formData, shared_alert_threshold: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                    min="50"
                    max="500"
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    Alert all members when any member's AQI crosses this threshold
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="auto_share_location"
                      checked={formData.auto_share_location}
                      onChange={(e) => setFormData({ ...formData, auto_share_location: e.target.checked })}
                      className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                    />
                    <label htmlFor="auto_share_location" className="text-sm text-gray-700">
                      Automatically share location updates with family
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="emergency_mode"
                      checked={formData.emergency_mode}
                      onChange={(e) => setFormData({ ...formData, emergency_mode: e.target.checked })}
                      className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                    />
                    <label htmlFor="emergency_mode" className="text-sm text-gray-700">
                      Enable emergency cascading alerts (Recommended)
                    </label>
                  </div>
                </div>

                <div className="flex gap-4 mt-6">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition font-semibold"
                  >
                    Create Group
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="grid md:grid-cols-3 gap-6">
          {/* Groups List */}
          <div className="md:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">Your Groups</h2>
              
              {groups.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-2">👨‍👩‍👧‍👦</div>
                  <p className="text-gray-600 text-sm mb-4">No groups yet</p>
                  <button
                    onClick={() => setShowCreateForm(true)}
                    className="px-4 py-2 bg-purple-100 hover:bg-purple-200 text-purple-800 rounded-lg transition text-sm font-medium"
                  >
                    Create First Group
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {groups.map((group) => (
                    <button
                      key={group.id}
                      onClick={() => handleSelectGroup(group.id)}
                      className={`w-full text-left p-4 rounded-lg transition ${
                        selectedGroup === group.id
                          ? 'bg-purple-100 border-2 border-purple-500'
                          : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-bold text-gray-900">{group.group_name}</h3>
                        <span className={`text-xs px-2 py-1 rounded-full ${getRoleBadgeColor(group.user_role)}`}>
                          {getRoleIcon(group.user_role)} {group.user_role}
                        </span>
                      </div>
                      {group.description && (
                        <p className="text-sm text-gray-600 line-clamp-2">{group.description}</p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                        {group.emergency_mode && <span>🚨 Emergency Mode</span>}
                        {group.auto_share_location && <span>📍 Location Sharing</span>}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Group Details & Members */}
          <div className="md:col-span-2">
            {selectedGroup ? (
              <div className="bg-white rounded-2xl shadow-lg p-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-2xl font-bold mb-2">
                      {groups.find(g => g.id === selectedGroup)?.group_name}
                    </h2>
                    <p className="text-gray-600">
                      {groups.find(g => g.id === selectedGroup)?.description || 'No description'}
                    </p>
                  </div>
                  <div className="text-sm text-gray-500">
                    Threshold: <span className="font-semibold text-orange-600">
                      {groups.find(g => g.id === selectedGroup)?.shared_alert_threshold} AQI
                    </span>
                  </div>
                </div>

                <h3 className="font-bold text-lg mb-4">Group Members ({groupMembers.length})</h3>
                
                {groupMembers.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-gray-600">No members yet. Invite family members to join!</p>
                  </div>
                ) : (
                  <div className="grid gap-4">
                    {groupMembers.map((member) => (
                      <div
                        key={member.id}
                        className="border border-gray-200 rounded-xl p-4 hover:shadow-md transition"
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex items-center gap-3">
                            <div className="w-12 h-12 bg-gradient-to-br from-purple-400 to-pink-400 rounded-full flex items-center justify-center text-white text-xl font-bold">
                              {member.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <h4 className="font-bold text-gray-900">{member.name}</h4>
                              <div className="flex items-center gap-2 text-sm text-gray-600">
                                {member.email && <span>📧 {member.email}</span>}
                                {member.phone && <span>📱 {member.phone}</span>}
                              </div>
                            </div>
                          </div>
                          <span className={`text-xs px-3 py-1 rounded-full ${getRoleBadgeColor(member.role)}`}>
                            {getRoleIcon(member.role)} {member.role}
                          </span>
                        </div>
                        
                        <div className="mt-3 flex items-center gap-4 text-sm">
                          <span className="text-gray-600">
                            <span className="font-medium">Condition:</span> {member.condition.toUpperCase()} ({member.severity})
                          </span>
                          {member.notifications_enabled && (
                            <span className="text-green-600">🔔 Notifications On</span>
                          )}
                        </div>
                        
                        <div className="mt-2 text-xs text-gray-500">
                          Joined on {new Date(member.joined_at).toLocaleDateString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
                <div className="text-6xl mb-4">👈</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-2">Select a Family Group</h3>
                <p className="text-gray-600">
                  Choose a group from the left to view members and details
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-8 bg-purple-50 border border-purple-200 rounded-2xl p-6">
          <h3 className="font-bold text-purple-900 mb-2">💡 How Family Groups Work</h3>
          <ul className="space-y-2 text-sm text-purple-800">
            <li>• All family members receive WhatsApp notifications when any member experiences high/critical AQI</li>
            <li>• Emergency mode enables automatic cascading alerts during critical events</li>
            <li>• Location sharing helps family track each other's exposure to pollution</li>
            <li>• Admins can manage group settings and add/remove members</li>
            <li>• All alerts are logged and can be reviewed in the dashboard</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
