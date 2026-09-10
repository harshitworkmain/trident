// Dashboard JavaScript
let allRequests = [];
let allTeams = [];
let refreshInterval = null;

// NOTE: initializeDashboard() is called by platform.js when the dashboard tab is selected.
// Do not auto-init here to avoid loading data when the tab is not visible.

// Initialize dashboard data
async function initializeDashboard() {
    try {
        await Promise.all([
            loadStatistics(),
            loadRequests(),
            loadTeams(),
            loadROVStatus(),
            loadWearableStatus()
        ]);
        // Start live telemetry polling for the 6-card grid
        startTelemetryPolling();
        showSuccess('Dashboard loaded successfully!');
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showError('Failed to load dashboard data');
    }
}

// Load system statistics
async function loadStatistics() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('pendingRequests').textContent = data.data.pendingRequests || 0;
            document.getElementById('activeTeams').textContent = data.data.availableTeams || 0;
            
            // Show emergency alert if high priority requests exist
            const alertStatus = document.getElementById('alertStatus');
            if (data.data.highPriorityRequests > 0) {
                alertStatus.style.display = 'flex';
                alertStatus.querySelector('span').textContent = `${data.data.highPriorityRequests} High Priority`;
            } else {
                alertStatus.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Load SOS requests
async function loadRequests() {
    try {
        const response = await fetch('/api/sos');
        const data = await response.json();
        
        if (data.success) {
            allRequests = data.data;
            displayRequests(allRequests);
        }
    } catch (error) {
        console.error('Error loading requests:', error);
        showError('Failed to load SOS requests');
    }
}

// Display requests in table
function displayRequests(requests) {
    const tableBody = document.getElementById('requestsTableBody');
    tableBody.innerHTML = '';
    
    requests.forEach(request => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${request.referenceId}</strong></td>
            <td>${request.name}</td>
            <td>${request.city}</td>
            <td>${formatEmergencyType(request.emergencyType)}</td>
            <td><span class="priority-badge priority-${request.priority}">Priority ${request.priority}</span></td>
            <td><span class="status-badge status-${request.status}">${formatStatus(request.status)}</span></td>
            <td>${getAssignedTeam(request.referenceId)}</td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn btn-view" onclick="viewRequest('${request.referenceId}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${request.status === 'pending' ? `
                        <button class="action-btn btn-assign" onclick="openAssignModal('${request.referenceId}')">
                            <i class="fas fa-user-plus"></i>
                        </button>
                    ` : ''}
                    <button class="action-btn btn-update" onclick="openStatusModal('${request.referenceId}')">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// Load response teams
async function loadTeams() {
    try {
        const response = await fetch('/api/response-teams');
        const data = await response.json();
        
        if (data.success) {
            allTeams = data.data;
            populateTeamSelect();
        }
    } catch (error) {
        console.error('Error loading teams:', error);
    }
}

// Populate team selection dropdown
function populateTeamSelect() {
    const select = document.getElementById('teamSelect');
    select.innerHTML = '<option value="">Choose available response team...</option>';
    
    allTeams.forEach(team => {
        if (team.isAvailable) {
            const option = document.createElement('option');
            option.value = team.id; // Use team ID instead of name
            
            // Show team type and deployment mode instead of incorrect capacity
            let teamInfo = '';
            if (team.teamType === 'ROV Water Rescue') {
                if (team.teamName.includes('Alpha')) {
                    teamInfo = '🚁 Auto-Deploy ROV Team';
                } else {
                    teamInfo = '🚁 Manual-Deploy ROV Team';
                }
            } else if (team.teamType === 'Water Emergency Supply') {
                teamInfo = '📦 Water Supply Team';
            } else {
                teamInfo = team.teamType;
            }
            
            option.textContent = `${team.teamName} - ${teamInfo}`;
            select.appendChild(option);
        }
    });
    
    // Add message if no teams available
    if (select.children.length === 1) {
        const option = document.createElement('option');
        option.value = "";
        option.textContent = "⚠️ No teams currently available";
        option.disabled = true;
        select.appendChild(option);
    }
}

// Load ROV status
async function loadROVStatus() {
    try {
        const response = await fetch('/api/rov-status');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('deployedROVs').textContent = data.data.deployed_rovs || 0;
            displayROVs(data.data.rovs || []);
        }
    } catch (error) {
        console.error('Error loading ROV status:', error);
    }
}

// Display ROV devices
function displayROVs(rovs) {
    const rovList = document.getElementById('rovList');
    rovList.innerHTML = '';
    
    rovs.forEach(rov => {
        const item = document.createElement('div');
        item.className = 'device-item';
        item.innerHTML = `
            <div class="device-info">
                <div class="device-icon device-rov">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="device-details">
                    <h4>${rov.name}</h4>
                    <p>Status: ${rov.status.charAt(0).toUpperCase() + rov.status.slice(1)}</p>
                    ${rov.assigned_request ? `<p>Request: ${rov.assigned_request}</p>` : ''}
                </div>
            </div>
            <div class="device-status">
                <div class="battery-indicator">
                    Battery: ${rov.battery}%
                    <div class="battery-bar">
                        <div class="battery-fill ${getBatteryClass(rov.battery)}" style="width: ${rov.battery}%"></div>
                    </div>
                </div>
            </div>
        `;
        rovList.appendChild(item);
    });
}

// Load wearable device status
async function loadWearableStatus() {
    try {
        const response = await fetch('/api/wearable-devices');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('connectedWearables').textContent = data.data.online_devices || 0;
            displayWearables(data.data.devices || []);
        }
    } catch (error) {
        console.error('Error loading wearable status:', error);
    }
}

// Display wearable devices
function displayWearables(devices) {
    const wearableList = document.getElementById('wearableList');
    wearableList.innerHTML = '';
    
    devices.forEach(device => {
        const item = document.createElement('div');
        item.className = 'device-item';
        const iconClass = device.status === 'emergency' ? 'device-emergency' : 'device-wearable';
        
        item.innerHTML = `
            <div class="device-info">
                <div class="device-icon ${iconClass}">
                    <i class="fas fa-heartbeat"></i>
                </div>
                <div class="device-details">
                    <h4>${device.user_name}</h4>
                    <p>Status: ${device.status.charAt(0).toUpperCase() + device.status.slice(1)}</p>
                    ${device.emergency_type ? `<p>Alert: ${device.emergency_type}</p>` : ''}
                </div>
            </div>
            <div class="device-status">
                <div class="battery-indicator">
                    Battery: ${device.battery}%
                    <div class="battery-bar">
                        <div class="battery-fill ${getBatteryClass(device.battery)}" style="width: ${device.battery}%"></div>
                    </div>
                </div>
            </div>
        `;
        wearableList.appendChild(item);
    });
}

// Filter and search requests
function filterRequests() {
    const statusFilter = document.getElementById('statusFilter').value;
    const priorityFilter = document.getElementById('priorityFilter').value;
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    
    let filteredRequests = allRequests.filter(request => {
        const matchesStatus = !statusFilter || request.status === statusFilter;
        const matchesPriority = !priorityFilter || request.priority.toString() === priorityFilter;
        const matchesSearch = !searchTerm || 
            request.name.toLowerCase().includes(searchTerm) ||
            request.city.toLowerCase().includes(searchTerm) ||
            request.referenceId.toLowerCase().includes(searchTerm);
        
        return matchesStatus && matchesPriority && matchesSearch;
    });
    
    displayRequests(filteredRequests);
}

// View request details
async function viewRequest(referenceId) {
    try {
        const response = await fetch(`/api/sos/${referenceId}`);
        const data = await response.json();
        
        if (data.success) {
            const request = allRequests.find(r => r.referenceId === referenceId);
            document.getElementById('requestDetails').innerHTML = `
                <div class="request-detail-grid">
                    <div class="detail-group">
                        <h4>Personal Information</h4>
                        <p><strong>Name:</strong> ${request.name}</p>
                        <p><strong>Age:</strong> ${request.age}</p>
                        <p><strong>Phone:</strong> ${request.phone}</p>
                        ${request.email ? `<p><strong>Email:</strong> ${request.email}</p>` : ''}
                    </div>
                    
                    <div class="detail-group">
                        <h4>Location</h4>
                        <p><strong>Address:</strong> ${request.address}</p>
                        <p><strong>City:</strong> ${request.city}</p>
                    </div>
                    
                    <div class="detail-group">
                        <h4>Emergency Details</h4>
                        <p><strong>Type:</strong> ${formatEmergencyType(request.emergencyType)}</p>
                        <p><strong>People to Rescue:</strong> ${request.peopleToRescue}</p>
                        <p><strong>People Injured:</strong> ${request.peopleInjured}</p>
                        <p><strong>Priority:</strong> ${request.priority}</p>
                        <p><strong>Status:</strong> ${formatStatus(request.status)}</p>
                    </div>
                    
                    <div class="detail-group">
                        <h4>Resources</h4>
                        <p><strong>Food Availability:</strong> ${request.foodAvailability}</p>
                        <p><strong>Water Availability:</strong> ${request.waterAvailability}</p>
                    </div>
                    
                    ${request.additionalInfo ? `
                        <div class="detail-group full-width">
                            <h4>Additional Information</h4>
                            <p>${request.additionalInfo}</p>
                        </div>
                    ` : ''}
                </div>
            `;
            document.getElementById('requestModal').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading request details:', error);
        showError('Failed to load request details');
    }
}

// Open assign team modal
function openAssignModal(referenceId) {
    document.getElementById('assignRequestId').value = referenceId;
    document.getElementById('assignModal').style.display = 'block';
}

// Open status update modal
function openStatusModal(referenceId) {
    document.getElementById('statusRequestId').value = referenceId;
    document.getElementById('statusModal').style.display = 'block';
}

// Assign team to request
async function assignTeam(event) {
    event.preventDefault();
    
    const referenceId = document.getElementById('assignRequestId').value;
    const teamId = document.getElementById('teamSelect').value;
    const notes = document.getElementById('assignmentNotes').value;
    
    try {
        const response = await fetch(`/api/sos/${referenceId}/assign-team`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                team_id: teamId, // Use numeric team ID
                assigned_by: 'Dashboard Operator',
                notes: notes
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess(`Team assigned successfully!`);
            closeModal('assignModal');
            await loadRequests();
            await loadStatistics();
        } else {
            showError(data.message || 'Failed to assign team');
        }
    } catch (error) {
        console.error('Error assigning team:', error);
        showError('Failed to assign team');
    }
}

// Update request status
async function updateStatus(event) {
    event.preventDefault();
    
    const referenceId = document.getElementById('statusRequestId').value;
    const newStatus = document.getElementById('newStatus').value;
    const notes = document.getElementById('statusNotes').value;
    
    try {
        const response = await fetch(`/api/sos/${referenceId}/update-status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                status: newStatus,
                notes: notes,
                updated_by: 'Dashboard Operator'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess('Status updated successfully!');
            closeModal('statusModal');
            await loadRequests();
            await loadStatistics();
        } else {
            showError(data.message || 'Failed to update status');
        }
    } catch (error) {
        console.error('Error updating status:', error);
        showError('Failed to update status');
    }
}

// Close modal
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Refresh functions
async function refreshRequests() {
    await loadRequests();
    await loadStatistics();
    showSuccess('Requests refreshed!');
}

async function refreshROVStatus() {
    await loadROVStatus();
    showSuccess('ROV status refreshed!');
}

async function refreshWearableStatus() {
    await loadWearableStatus();
    showSuccess('Wearable status refreshed!');
}

// ═══════════════════════════════════════════════════════════════════════════
//  LIVE WEARABLE TELEMETRY POLLING & 6-CARD DOM UPDATER
// ═══════════════════════════════════════════════════════════════════════════

let telemetryInterval = null;

function startTelemetryPolling() {
    // Initial fetch
    fetchAndUpdateTelemetry();
    // Poll every 1.5 seconds
    if (telemetryInterval) clearInterval(telemetryInterval);
    telemetryInterval = setInterval(fetchAndUpdateTelemetry, 1500);
}

function stopTelemetryPolling() {
    if (telemetryInterval) {
        clearInterval(telemetryInterval);
        telemetryInterval = null;
    }
}

async function fetchAndUpdateTelemetry() {
    try {
        const response = await fetch('/api/telemetry/wearable/latest');
        const result = await response.json();
        
        if (result.success && result.data && result.data.length > 0) {
            // Use the first (or primary) device's telemetry
            const d = result.data[0];
            updateTelemetryCards(d);
        } else {
            // No devices reporting yet — show waiting state
            updateTelemetryConnectionStatus(false);
        }
    } catch (error) {
        console.error('Telemetry fetch error:', error);
        updateTelemetryConnectionStatus(false);
    }
}

function updateTelemetryCards(d) {
    const isOnline = d.is_online || false;
    updateTelemetryConnectionStatus(isOnline, d.device_id);
    
    // Card 1: System Hardware Status
    const sysBody = document.getElementById('systemStatusBody');
    if (sysBody) {
        sysBody.innerHTML = 
            `MPU6050: ${statusBadge(d.mpu_ok)}<br>` +
            `MAX30102: ${statusBadge(d.max_ok)}<br>` +
            `GSR: ${statusBadge(d.gsr_ok)}<br>` +
            `GPS: ${d.gps_ok ? '<span class="telem-ok">Fix Acquired</span>' : '<span class="telem-warn">Searching...</span>'}<br>` +
            `Wi-Fi: ${d.wifi_ok ? '<span class="telem-ok">Connected</span>' : '<span class="telem-warn">Offline</span>'}`;
    }
    
    // Card 2: Fall Detection
    const accEl = document.getElementById('accMagVal');
    const gyroEl = document.getElementById('gyroMagVal');
    const fallBadge = document.getElementById('fallStatusBadge');
    const fallReset = document.getElementById('fallResetContainer');
    const fallCard = document.getElementById('cardFall');
    
    if (accEl) accEl.textContent = (d.acc_mag || 0).toFixed(2);
    if (gyroEl) gyroEl.textContent = (d.gyro_mag || 0).toFixed(2);
    
    if (fallBadge) {
        if (d.fall_detected) {
            fallBadge.className = 'telem-bad';
            fallBadge.textContent = 'FALL DETECTED';
            if (fallReset) fallReset.style.display = 'block';
            if (fallCard) fallCard.classList.add('emergency-flash');
        } else {
            fallBadge.className = 'telem-ok';
            fallBadge.textContent = 'Normal';
            if (fallReset) fallReset.style.display = 'none';
            if (fallCard) fallCard.classList.remove('emergency-flash');
        }
    }
    
    // Card 3: GPS & Geofence
    setTextById('gpsLat', (d.lat || 0).toFixed(6));
    setTextById('gpsLng', (d.lng || 0).toFixed(6));
    setTextById('gpsSats', d.satellites || 0);
    setTextById('safeLat', (d.safe_lat || 0).toFixed(6));
    setTextById('safeLng', (d.safe_lng || 0).toFixed(6));
    
    const geoBadge = document.getElementById('geoStatusBadge');
    const gpsCard = document.getElementById('cardGPS');
    if (geoBadge) {
        if (d.geo_breached) {
            geoBadge.className = 'telem-bad';
            geoBadge.textContent = 'OUTSIDE FENCE';
            if (gpsCard) gpsCard.classList.add('emergency-flash');
        } else {
            geoBadge.className = 'telem-ok';
            geoBadge.textContent = 'Inside Fence';
            if (gpsCard) gpsCard.classList.remove('emergency-flash');
        }
    }
    
    // Card 4: Update geofence config inputs with current values
    const geoLatInput = document.getElementById('geoConfigLat');
    const geoLngInput = document.getElementById('geoConfigLng');
    const geoRadInput = document.getElementById('geoConfigRad');
    // Only update if user is not currently editing
    if (geoLatInput && document.activeElement !== geoLatInput) geoLatInput.value = (d.safe_lat || 12.8239).toFixed(6);
    if (geoLngInput && document.activeElement !== geoLngInput) geoLngInput.value = (d.safe_lng || 80.0467).toFixed(6);
    if (geoRadInput && document.activeElement !== geoRadInput) geoRadInput.value = d.geo_radius_km || 0.1;
    
    // Card 5: Vitals
    setTextById('bpmVal', Math.round(d.bpm || 0));
    setTextById('spo2Val', (d.spo2 || 0).toFixed(1));
    
    const vitalsBadge = document.getElementById('vitalsCatBadge');
    if (vitalsBadge) {
        const cat = d.vitals_cat || 'Unknown';
        if (cat === 'Critical') { vitalsBadge.className = 'telem-bad'; vitalsBadge.textContent = 'Critical'; }
        else if (cat === 'Warning') { vitalsBadge.className = 'telem-warn'; vitalsBadge.textContent = 'Warning'; }
        else if (cat === 'No Finger') { vitalsBadge.className = 'telem-warn'; vitalsBadge.textContent = 'No Finger'; }
        else if (cat === 'Normal') { vitalsBadge.className = 'telem-ok'; vitalsBadge.textContent = 'Normal'; }
        else { vitalsBadge.className = 'telem-warn'; vitalsBadge.textContent = cat; }
    }
    
    // Card 6: GSR / Stress
    setTextById('gsrRawVal', Math.round(d.gsr_raw || 0));
    
    const stressBadge = document.getElementById('stressLevelBadge');
    if (stressBadge) {
        const lvl = d.stress_level || 'Unknown';
        if (lvl === 'High') { stressBadge.className = 'telem-bad'; stressBadge.textContent = 'High'; }
        else if (lvl === 'Medium') { stressBadge.className = 'telem-warn'; stressBadge.textContent = 'Medium'; }
        else if (lvl === 'Low') { stressBadge.className = 'telem-ok'; stressBadge.textContent = 'Low'; }
        else { stressBadge.className = 'telem-warn'; stressBadge.textContent = lvl; }
    }
}

function updateTelemetryConnectionStatus(isOnline, deviceId) {
    const dot = document.getElementById('telemetryDot');
    const statusText = document.getElementById('telemetryConnectionStatus');
    
    if (dot) {
        dot.className = isOnline ? 'telemetry-dot online' : 'telemetry-dot offline';
    }
    if (statusText) {
        statusText.textContent = isOnline 
            ? `${deviceId || 'Device'} • Connected` 
            : 'Waiting for device...';
    }
}

function statusBadge(ok) {
    return ok ? '<span class="telem-ok">OK</span>' : '<span class="telem-warn">Not Detected</span>';
}

function setTextById(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// ── Remote Wearable Control Commands ──

async function sendWearableCommand(action) {
    try {
        const response = await fetch('/api/wearable/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: 'TRIDENT-WEAR-01',
                action: action,
                params: {}
            })
        });
        const result = await response.json();
        if (result.success) {
            showSuccess(`Command '${action}' sent to wearable`);
        } else {
            showError(result.message || 'Failed to send command');
        }
    } catch (error) {
        console.error('Error sending wearable command:', error);
        showError('Failed to send command to wearable');
    }
}

async function sendGeofenceUpdate() {
    const lat = parseFloat(document.getElementById('geoConfigLat').value);
    const lng = parseFloat(document.getElementById('geoConfigLng').value);
    const rad = parseFloat(document.getElementById('geoConfigRad').value);
    
    if (isNaN(lat) || isNaN(lng) || isNaN(rad) || rad <= 0) {
        showError('Invalid geofence parameters');
        return;
    }
    
    try {
        const response = await fetch('/api/wearable/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: 'TRIDENT-WEAR-01',
                action: 'set_geofence',
                params: { latitude: lat, longitude: lng, radius: rad }
            })
        });
        const result = await response.json();
        if (result.success) {
            showSuccess('Geofence update command queued');
        } else {
            showError(result.message || 'Failed to update geofence');
        }
    } catch (error) {
        console.error('Error sending geofence update:', error);
        showError('Failed to update geofence');
    }
}

// Helper functions
function formatEmergencyType(type) {
    return type.charAt(0).toUpperCase() + type.slice(1);
}

function formatStatus(status) {
    return status.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function getBatteryClass(battery) {
    if (battery > 60) return 'battery-high';
    if (battery > 30) return 'battery-medium';
    return 'battery-low';
}

function getAssignedTeam(referenceId) {
    const request = allRequests.find(r => r.referenceId === referenceId);
    return request && request.assignedTeam ? request.assignedTeam : 'Not assigned';
}

// Auto-refresh setup (30s for stats/ROV/wearable list; telemetry grid uses its own 1.5s interval)
function setupAutoRefresh() {
    refreshInterval = setInterval(async () => {
        await loadStatistics();
        await loadROVStatus();
        await loadWearableStatus();
    }, 30000);
}

// Success/error notifications
function showSuccess(message) {
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'error');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'check-circle'}"></i>
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#ef4444' : '#10b981'};
        color: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        z-index: 3000;
        max-width: 400px;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Close modals when clicking outside
window.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// Add CSS animations
(function() { const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .notification-close {
        background: none;
        border: none;
        color: white;
        cursor: pointer;
        margin-left: auto;
        padding: 0.25rem;
    }
    
    .request-detail-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1.5rem;
    }
    
    .detail-group h4 {
        margin: 0 0 1rem 0;
        color: #1e293b;
        font-weight: 600;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.5rem;
    }
    
    .detail-group p {
        margin: 0.5rem 0;
        color: #64748b;
    }
    
    .detail-group strong {
        color: #374151;
    }
    
    .full-width {
        grid-column: 1 / -1;
    }
`;
document.head.appendChild(style); })();