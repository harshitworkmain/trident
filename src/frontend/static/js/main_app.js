// DOM Elements
const sosForm = document.getElementById('sosForm');
const successModal = document.getElementById('successModal');
const referenceIdSpan = document.getElementById('referenceId');

// Navigation
document.addEventListener('DOMContentLoaded', function() {
    // Initialize modern UI features
    initializeModernUI();
    
    // Smooth scrolling for navigation links
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            
            if (targetSection) {
                targetSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                
                // Update active nav link
                navLinks.forEach(l => l.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });

    // Update active nav link on scroll
    window.addEventListener('scroll', updateActiveNavLink);
    
    // Form validation
    setupFormValidation();
    
    // Auto-save form data to localStorage
    setupAutoSave();
    
    // Add modern interactions
    addModernInteractions();
    
    // Load hero stats
    loadHeroStats();
});

// Initialize modern UI features
function initializeModernUI() {
    // Add scroll effect to header
    const header = document.querySelector('.header');
    let lastScrollY = window.scrollY;
    
    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;
        
        if (currentScrollY > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
        
        lastScrollY = currentScrollY;
    });
    
    // Add parallax effect to hero section
    const hero = document.querySelector('.hero');
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const rate = scrolled * -0.5;
        hero.style.transform = `translateY(${rate}px)`;
    });
    
    // Add intersection observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observe form sections for animations
    document.querySelectorAll('.form-section').forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(30px)';
        section.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(section);
    });
}

// Update active navigation link based on scroll position
function updateActiveNavLink() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');
    
    let current = '';
    sections.forEach(section => {
        const sectionTop = section.offsetTop - 100;
        const sectionHeight = section.clientHeight;
        if (window.pageYOffset >= sectionTop && window.pageYOffset < sectionTop + sectionHeight) {
            current = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${current}`) {
            link.classList.add('active');
        }
    });
}

// Form validation setup
function setupFormValidation() {
    const form = document.getElementById('sosForm');
    const inputs = form.querySelectorAll('input, select, textarea');
    
    inputs.forEach(input => {
        input.addEventListener('blur', validateField);
        input.addEventListener('input', clearFieldError);
    });
}

// Validate individual field
function validateField(e) {
    const field = e.target;
    const value = field.value.trim();
    
    // Remove existing error message
    clearFieldError(e);
    
    // Required field validation
    if (field.hasAttribute('required') && !value) {
        showFieldError(field, 'This field is required');
        return false;
    }
    
    // Specific validations
    switch (field.type) {
        case 'email':
            if (value && !isValidEmail(value)) {
                showFieldError(field, 'Please enter a valid email address');
                return false;
            }
            break;
        case 'tel':
            if (value && !isValidPhone(value)) {
                showFieldError(field, 'Please enter a valid phone number');
                return false;
            }
            break;
        case 'number':
            if (value) {
                const num = parseInt(value);
                if (field.id === 'age' && (num < 1 || num > 120)) {
                    showFieldError(field, 'Please enter a valid age (1-120)');
                    return false;
                }
                if (field.id === 'peopleToRescue' && num < 1) {
                    showFieldError(field, 'At least 1 person must need rescue');
                    return false;
                }
                if (field.id === 'peopleInjured' && num < 0) {
                    showFieldError(field, 'Number of injured cannot be negative');
                    return false;
                }
            }
            break;
    }
    
    return true;
}

// Show field error
function showFieldError(field, message) {
    field.style.borderColor = '#ef4444';
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    field.parentNode.appendChild(errorDiv);
}

// Clear field error
function clearFieldError(e) {
    const field = e.target;
    field.style.borderColor = '#e2e8f0';
    
    const errorMessage = field.parentNode.querySelector('.error-message');
    if (errorMessage) {
        errorMessage.remove();
    }
}

// Email validation
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Phone validation
function isValidPhone(phone) {
    const phoneRegex = /^[\+]?[1-9][\d]{0,15}$/;
    return phoneRegex.test(phone.replace(/\s/g, ''));
}

// Auto-save form data
function setupAutoSave() {
    const form = document.getElementById('sosForm');
    const inputs = form.querySelectorAll('input, select, textarea');
    
    // Load saved data
    loadSavedData();
    
    // Save data on input
    inputs.forEach(input => {
        input.addEventListener('input', saveFormData);
        input.addEventListener('change', saveFormData);
    });
}

// Save form data to localStorage
function saveFormData() {
    const form = document.getElementById('sosForm');
    const formData = new FormData(form);
    const data = {};
    
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    
    // Save checkboxes and radio buttons
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    const radios = form.querySelectorAll('input[type="radio"]');
    
    checkboxes.forEach(checkbox => {
        data[checkbox.name] = checkbox.checked;
    });
    
    radios.forEach(radio => {
        if (radio.checked) {
            data[radio.name] = radio.value;
        }
    });
    
    localStorage.setItem('trident_sos_form', JSON.stringify(data));
}

// Load saved form data
function loadSavedData() {
    const savedData = localStorage.getItem('trident_sos_form');
    if (!savedData) return;
    
    try {
        const data = JSON.parse(savedData);
        const form = document.getElementById('sosForm');
        
        Object.keys(data).forEach(key => {
            const field = form.querySelector(`[name="${key}"]`);
            if (field) {
                if (field.type === 'checkbox') {
                    field.checked = data[key];
                } else if (field.type === 'radio') {
                    if (field.value === data[key]) {
                        field.checked = true;
                    }
                } else {
                    field.value = data[key];
                }
            }
        });
    } catch (error) {
        console.error('Error loading saved form data:', error);
    }
}

// Clear form data
function clearForm() {
    if (confirm('Are you sure you want to clear all form data?')) {
        const form = document.getElementById('sosForm');
        form.reset();
        localStorage.removeItem('trident_sos_form');
        
        // Clear any error messages
        const errorMessages = form.querySelectorAll('.error-message');
        errorMessages.forEach(msg => msg.remove());
        
        // Reset field borders
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.style.borderColor = '#e2e8f0';
        });
    }
}

// Form submission
sosForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // Validate all fields
    const inputs = this.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!validateField({ target: input })) {
            isValid = false;
        }
    });
    
    if (!isValid) {
        showNotification('Please fix the errors in the form before submitting.', 'error');
        return;
    }
    
    // Show loading state
    const submitBtn = this.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="loading"></span> Sending SOS...';
    submitBtn.disabled = true;
    
    try {
        // Collect form data
        const formData = new FormData(this);
        const sosData = {};
        
        for (let [key, value] of formData.entries()) {
            sosData[key] = value;
        }
        
        // Add checkboxes and radio buttons
        const checkboxes = this.querySelectorAll('input[type="checkbox"]');
        const radios = this.querySelectorAll('input[type="radio"]');
        
        checkboxes.forEach(checkbox => {
            sosData[checkbox.name] = checkbox.checked;
        });
        
        radios.forEach(radio => {
            if (radio.checked) {
                sosData[radio.name] = radio.value;
            }
        });
        
        // Add timestamp and location
        sosData.timestamp = new Date().toISOString();
        sosData.userAgent = navigator.userAgent;
        
        // Try to get location
        if (navigator.geolocation) {
            try {
                const position = await getCurrentPosition();
                sosData.latitude = position.coords.latitude;
                sosData.longitude = position.coords.longitude;
            } catch (error) {
                console.warn('Could not get location:', error);
            }
        }
        
        // Send SOS request
        const response = await sendSOSRequest(sosData);
        
        if (response.success) {
            // Show success modal
            referenceIdSpan.textContent = response.referenceId;
            successModal.style.display = 'block';
            
            // Clear form and saved data
            this.reset();
            localStorage.removeItem('trident_sos_form');
            
            // Send notification to emergency services (simulated)
            await notifyEmergencyServices(sosData, response.referenceId);
            
        } else {
            throw new Error(response.message || 'Failed to send SOS request');
        }
        
    } catch (error) {
        console.error('SOS submission error:', error);
        showNotification('Failed to send SOS request. Please try again or contact emergency services directly.', 'error');
    } finally {
        // Reset button
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
});

// Get current position
function getCurrentPosition() {
    return new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000
        });
    });
}

// Send SOS request to backend
async function sendSOSRequest(data) {
    try {
        const response = await fetch('/api/sos', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        throw new Error('Network error: ' + error.message);
    }
}

// Notify emergency services (simulated)
async function notifyEmergencyServices(data, referenceId) {
    // Simulate notification to emergency services
    console.log('Notifying emergency services:', {
        referenceId: referenceId,
        emergencyType: data.emergencyType,
        location: data.address,
        peopleToRescue: data.peopleToRescue,
        peopleInjured: data.peopleInjured,
        priority: calculatePriority(data)
    });
    
    // In a real implementation, this would send notifications to:
    // - Local emergency services
    // - Rescue teams
    // - Medical services
    // - Government disaster management
}

// Calculate priority based on form data
function calculatePriority(data) {
    let priority = 1; // Low priority by default
    
    // High priority factors
    if (parseInt(data.peopleInjured) > 0) priority += 2;
    if (data.pregnant === 'true') priority += 1;
    if (data.elderly === 'true') priority += 1;
    if (data.children === 'true') priority += 1;
    if (data.disabled === 'true') priority += 1;
    if (data.medical === 'true') priority += 2;
    if (data.foodAvailability === 'none' || data.foodAvailability === 'critical') priority += 1;
    if (data.waterAvailability === 'none' || data.waterAvailability === 'critical') priority += 1;
    
    // Emergency type priority (water-related emergencies)
    if (data.emergencyType === 'tsunami') priority += 3; // Highest water emergency priority
    if (data.emergencyType === 'dam-breach') priority += 3; // Extremely dangerous
    if (data.emergencyType === 'flood') priority += 2; // High priority
    if (data.emergencyType === 'storm') priority += 2; // High priority during severe weather
    if (data.emergencyType === 'water-level-rising') priority += 2; // Imminent danger
    if (data.emergencyType === 'coastal-erosion') priority += 1; // Lower but still urgent
    
    return Math.min(priority, 5); // Max priority 5
}

// Close modal
function closeModal() {
    successModal.style.display = 'none';
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        z-index: 3000;
        max-width: 400px;
        animation: slideInRight 0.3s ease;
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Add CSS for notification animation
const style = document.createElement('style');
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
`;
document.head.appendChild(style);

// Close modal when clicking outside
window.addEventListener('click', function(e) {
    if (e.target === successModal) {
        closeModal();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // ESC to close modal
    if (e.key === 'Escape' && successModal.style.display === 'block') {
        closeModal();
    }
    
    // Ctrl+Enter to submit form
    if (e.ctrlKey && e.key === 'Enter') {
        const form = document.getElementById('sosForm');
        if (form) {
            form.dispatchEvent(new Event('submit'));
        }
    }
});

// Add modern interactions
function addModernInteractions() {
    // Add ripple effect to buttons
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // Add typing animation to hero title
    const heroTitle = document.querySelector('.hero-title');
    if (heroTitle) {
        const text = heroTitle.textContent;
        heroTitle.textContent = '';
        heroTitle.style.borderRight = '2px solid white';
        
        let i = 0;
        const typeWriter = () => {
            if (i < text.length) {
                heroTitle.textContent += text.charAt(i);
                i++;
                setTimeout(typeWriter, 100);
            } else {
                setTimeout(() => {
                    heroTitle.style.borderRight = 'none';
                }, 1000);
            }
        };
        
        setTimeout(typeWriter, 500);
    }
    
    // Add floating labels to form inputs
    document.querySelectorAll('.form-group input, .form-group textarea, .form-group select').forEach(input => {
        const label = input.previousElementSibling;
        if (label && label.tagName === 'LABEL') {
            input.addEventListener('focus', () => {
                label.style.transform = 'translateY(-8px) scale(0.9)';
                label.style.color = 'var(--accent-color)';
            });
            
            input.addEventListener('blur', () => {
                if (!input.value) {
                    label.style.transform = 'translateY(0) scale(1)';
                    label.style.color = 'var(--text-secondary)';
                }
            });
            
            // Check if input has value on load
            if (input.value) {
                label.style.transform = 'translateY(-8px) scale(0.9)';
                label.style.color = 'var(--accent-color)';
            }
        }
    });
    
    // Add progress indicator to form
    const form = document.getElementById('sosForm');
    if (form) {
        const progressBar = document.createElement('div');
        progressBar.className = 'form-progress';
        progressBar.innerHTML = '<div class="progress-fill"></div>';
        form.insertBefore(progressBar, form.firstChild);
        
        const updateProgress = () => {
            const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
            const filled = Array.from(inputs).filter(input => input.value.trim() !== '').length;
            const progress = (filled / inputs.length) * 100;
            
            const progressFill = progressBar.querySelector('.progress-fill');
            progressFill.style.width = progress + '%';
        };
        
        form.addEventListener('input', updateProgress);
        form.addEventListener('change', updateProgress);
    }
}

// Load hero stats
async function loadHeroStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('totalRequests').textContent = data.data.totalSOSRequests;
            document.getElementById('activeTeams').textContent = data.data.availableTeams;
        }
    } catch (error) {
        console.error('Error loading hero stats:', error);
        // Set default values if API fails
        document.getElementById('totalRequests').textContent = '0';
        document.getElementById('activeTeams').textContent = '5';
    }
}

// Service Worker registration for offline functionality
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registration successful');
            })
            .catch(function(err) {
                console.log('ServiceWorker registration failed');
            });
    });
}
