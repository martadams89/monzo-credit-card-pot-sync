/**
 * Form validation and submission handlers
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all forms with validation
    const forms = document.querySelectorAll('form[data-validate="true"]');
    forms.forEach(initializeFormValidation);
    
    // Initialize password strength meters
    const passwordInputs = document.querySelectorAll('input[data-password-strength]');
    passwordInputs.forEach(initializePasswordStrength);
    
    // Initialize form submission handlers
    const ajaxForms = document.querySelectorAll('form[data-ajax="true"]');
    ajaxForms.forEach(initializeAjaxSubmission);
});

/**
 * Initialize form validation
 * @param {HTMLFormElement} form - Form element to initialize
 */
function initializeFormValidation(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    
    // Add validation on form submission
    form.addEventListener('submit', function(event) {
        if (!validateForm(form)) {
            event.preventDefault();
            return false;
        }
    });
    
    // Add real-time validation for form fields
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            validateField(input);
        });
    });
}

/**
 * Initialize password strength meter
 * @param {HTMLInputElement} input - Password input element
 */
function initializePasswordStrength(input) {
    const container = document.createElement('div');
    container.className = 'password-strength mt-2';
    
    const meter = document.createElement('div');
    meter.className = 'w-full h-2 bg-gray-200 rounded dark:bg-gray-700';
    
    const indicator = document.createElement('div');
    indicator.className = 'h-2 rounded transition-all duration-300';
    indicator.style.width = '0%';
    meter.appendChild(indicator);
    
    const text = document.createElement('p');
    text.className = 'text-xs mt-1 text-gray-500 dark:text-gray-400';
    
    container.appendChild(meter);
    container.appendChild(text);
    input.parentNode.insertBefore(container, input.nextSibling);
    
    input.addEventListener('input', function() {
        updatePasswordStrength(input.value, indicator, text);
    });
}

/**
 * Update password strength indicator
 * @param {string} password - Password to evaluate
 * @param {HTMLElement} indicator - Strength indicator element
 * @param {HTMLElement} text - Text element to show strength message
 */
function updatePasswordStrength(password, indicator, text) {
    const strength = evaluatePasswordStrength(password);
    
    // Update indicator color and width
    indicator.style.width = strength.percent + '%';
    indicator.className = 'h-2 rounded ' + strength.colorClass;
    
    // Update text message
    text.textContent = strength.message;
}

/**
 * Evaluate password strength
 * @param {string} password - Password to evaluate
 * @returns {Object} Strength details
 */
function evaluatePasswordStrength(password) {
    if (!password) {
        return {
            score: 0,
            percent: 0,
            message: '',
            colorClass: 'bg-gray-200'
        };
    }
    
    let score = 0;
    
    // Length check
    if (password.length >= 8) score += 1;
    if (password.length >= 12) score += 1;
    
    // Complexity checks
    if (/[A-Z]/.test(password)) score += 1;
    if (/[a-z]/.test(password)) score += 1;
    if (/[0-9]/.test(password)) score += 1;
    if (/[^A-Za-z0-9]/.test(password)) score += 1;
    
    // Scoring
    const percent = Math.min(100, Math.round((score / 6) * 100));
    
    let colorClass = 'bg-red-500';
    let message = 'Weak';
    
    if (score >= 5) {
        colorClass = 'bg-green-500';
        message = 'Strong';
    } else if (score >= 3) {
        colorClass = 'bg-yellow-500';
        message = 'Moderate';
    } else if (score >= 2) {
        colorClass = 'bg-orange-500';
        message = 'Fair';
    }
    
    return {
        score: score,
        percent: percent,
        message: message,
        colorClass: colorClass
    };
}

/**
 * Validate a form
 * @param {HTMLFormElement} form - Form to validate
 * @returns {boolean} Whether the form is valid
 */
function validateForm(form) {
    const inputs = form.querySelectorAll('input, select, textarea');
    let isValid = true;
    
    inputs.forEach(function(input) {
        if (!validateField(input)) {
            isValid = false;
        }
    });
    
    return isValid;
}

/**
 * Validate a single form field
 * @param {HTMLElement} field - Field to validate
 * @returns {boolean} Whether the field is valid
 */
function validateField(field) {
    // Skip fields that don't need validation
    if (field.hasAttribute('readonly') || field.disabled || field.type === 'hidden') {
        return true;
    }
    
    const errorContainer = field.parentNode.querySelector('.error-message');
    if (errorContainer) {
        errorContainer.remove();
    }
    
    // Check for required fields
    if (field.required && !field.value.trim()) {
        showError(field, 'This field is required');
        return false;
    }
    
    // Email validation
    if (field.type === 'email' && field.value.trim()) {
        const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailPattern.test(field.value)) {
            showError(field, 'Please enter a valid email address');
            return false;
        }
    }
    
    // Password validation
    if (field.type === 'password' && field.hasAttribute('data-validate-password') && field.value.trim()) {
        const minLength = parseInt(field.getAttribute('data-min-length') || '8');
        if (field.value.length < minLength) {
            showError(field, `Password must be at least ${minLength} characters long`);
            return false;
        }
    }
    
    // Password confirmation validation
    if (field.hasAttribute('data-confirm-password')) {
        const passwordFieldId = field.getAttribute('data-confirm-password');
        const passwordField = document.getElementById(passwordFieldId);
        if (passwordField && field.value !== passwordField.value) {
            showError(field, 'Passwords do not match');
            return false;
        }
    }
    
    return true;
}

/**
 * Show error message for a field
 * @param {HTMLElement} field - Field with error
 * @param {string} message - Error message to show
 */
function showError(field, message) {
    const errorElement = document.createElement('p');
    errorElement.className = 'error-message mt-1 text-sm text-red-600 dark:text-red-500';
    errorElement.textContent = message;
    
    field.classList.add('border-red-500');
    field.parentNode.appendChild(errorElement);
}

/**
 * Initialize AJAX form submission
 * @param {HTMLFormElement} form - Form to handle with AJAX
 */
function initializeAjaxSubmission(form) {
    form.addEventListener('submit', function(event) {
        event.preventDefault();
        
        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = 'Processing...';
        
        const formData = new FormData(form);
        
        fetch(form.action, {
            method: form.method,
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
            
            if (data.success) {
                showFormSuccess(form, data.message || 'Operation completed successfully');
                if (data.redirect) {
                    window.location.href = data.redirect;
                } else if (form.hasAttribute('data-reset-on-success')) {
                    form.reset();
                }
            } else {
                showFormError(form, data.message || 'An error occurred');
            }
        })
        .catch(error => {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
            showFormError(form, 'An unexpected error occurred');
            console.error('Form submission error:', error);
        });
    });
}

/**
 * Show success message for form
 * @param {HTMLFormElement} form - Form element
 * @param {string} message - Success message to show
 */
function showFormSuccess(form, message) {
    const alertElement = createAlert(message, 'success');
    insertFormAlert(form, alertElement);
}

/**
 * Show error message for form
 * @param {HTMLFormElement} form - Form element
 * @param {string} message - Error message to show
 */
function showFormError(form, message) {
    const alertElement = createAlert(message, 'error');
    insertFormAlert(form, alertElement);
}

/**
 * Create an alert message element
 * @param {string} message - Message to display
 * @param {string} type - Alert type ('success', 'error', 'warning', 'info')
 * @returns {HTMLElement} Alert element
 */
function createAlert(message, type) {
    const alertClasses = {
        success: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
        error: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        warning: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
        info: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
    };
    
    const alertElement = document.createElement('div');
    alertElement.className = `form-alert p-4 mb-4 rounded-md ${alertClasses[type] || alertClasses.info}`;
    alertElement.textContent = message;
    
    return alertElement;
}

/**
 * Insert alert element into form
 * @param {HTMLFormElement} form - Form element
 * @param {HTMLElement} alertElement - Alert element to insert
 */
function insertFormAlert(form, alertElement) {
    // Remove any existing alerts
    const existingAlerts = form.querySelectorAll('.form-alert');
    existingAlerts.forEach(alert => alert.remove());
    
    // Insert at beginning of form
    form.insertBefore(alertElement, form.firstChild);
    
    // Auto-remove after a delay
    setTimeout(() => {
        alertElement.classList.add('opacity-0');
        setTimeout(() => {
            alertElement.remove();
        }, 300);
    }, 5000);
}
