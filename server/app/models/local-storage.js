// Local storage utility for managing conversation data
import debounce from 'lodash/debounce';

// Constants
const STORAGE_KEY_PREFIX = 'tg_portal_';
const CONVERSATIONS_STORAGE_KEY = `${STORAGE_KEY_PREFIX}conversations`;
const MAX_ITEMS_TO_STORE = 500; // Maximum number of conversation items to store

const STORAGE_VERSION = '1.1'; // Version for future compatibility


// Local storage has a limit of approximately 5-10MB depending on the browser

/**
 * Check if localStorage is available
 * @returns {boolean} True if localStorage is available
 */
export function isLocalStorageAvailable() {
    try {
        const testKey = `${STORAGE_KEY_PREFIX}_test`;
        localStorage.setItem(testKey, 'test');
        localStorage.removeItem(testKey);
        return true;
    } catch (e) {
        console.error('localStorage is not available:', e);
        return false;
    }
}

/**
 * Get an estimate of the current localStorage usage in bytes
 * @returns {number} Approximate size in bytes
 */
export function getLocalStorageSize() {
    let totalSize = 0;
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key.startsWith(STORAGE_KEY_PREFIX)) {
            const value = localStorage.getItem(key);
            totalSize += (key.length + value.length) * 2; // Approximate UTF-16 encoding (2 bytes per character)
        }
    }
    return totalSize;
}


/**
 * Save conversations data to localStorage with error handling
 * @param {Array} conversations The conversations array to save
 * @returns {boolean} True if save was successful
 */
export function saveConversationsToStorage(conversations) {
    if (!isLocalStorageAvailable() || !Array.isArray(conversations)) {
        console.warn('Local storage not available or invalid conversations array');
        return false;
    }

    try {
        // Filter out any invalid conversations
        const validConversations = conversations.filter(conv =>
            conv && typeof conv === 'object' && conv.conversation_id
        );

        // Create a storage object with metadata
        const storageObj = {
            version: STORAGE_VERSION,
            lastUpdated: new Date().toISOString(),
            data: validConversations
        };

        // Simple limit check - if we have too many conversations, keep only the newest ones
        if (validConversations.length > MAX_ITEMS_TO_STORE) {
            console.log(`Limiting stored conversations from ${validConversations.length} to ${MAX_ITEMS_TO_STORE}`);

            // Sort by last message time (newest first)
            validConversations.sort((a, b) => {
                const timeA = a.last_message_time ? new Date(a.last_message_time) : new Date(0);
                const timeB = b.last_message_time ? new Date(b.last_message_time) : new Date(0);
                return timeB - timeA;
            });

            // Keep only the most recent MAX_ITEMS_TO_STORE conversations
            storageObj.data = validConversations.slice(0, MAX_ITEMS_TO_STORE);
        }

        // Save to localStorage
        const json = JSON.stringify(storageObj);
        localStorage.setItem(CONVERSATIONS_STORAGE_KEY, json);
        console.log(`Successfully saved ${storageObj.data.length} conversations to localStorage`);
        return true;
    } catch (e) {
        console.error('Error saving to localStorage:', e);

        // For quota errors, try a basic cleanup
        if (e.name === 'QuotaExceededError' || e.code === 22) {
            try {
                // Simple cleanup - just remove the conversations storage entirely as a last resort
                localStorage.removeItem(CONVERSATIONS_STORAGE_KEY);
                console.warn('Storage quota exceeded, cleared conversations storage');
            } catch (cleanupError) {
                console.error('Failed to clean up localStorage:', cleanupError);
            }
        }

        return false;
    }
}

/**
 * Load conversations data from localStorage
 * @returns {Array} The conversations array or empty array if not found
 */
export function loadConversationsFromStorage() {
    if (!isLocalStorageAvailable()) {
        console.warn('Local storage is not available');
        return [];
    }

    try {
        const json = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
        if (!json) {
            console.log('No conversations found in local storage');
            return [];
        }

        const storageObj = JSON.parse(json);

        // Handle different versions if needed
        if (storageObj.version !== STORAGE_VERSION) {
            console.warn(`Storage version mismatch: ${storageObj.version} vs ${STORAGE_VERSION}`);
            // Could implement migration logic here if needed
        }

        // Validate data format
        if (!storageObj.data) {
            console.warn('Invalid storage format (missing data property)');
            return [];
        }

        if (!Array.isArray(storageObj.data)) {
            console.warn('Invalid storage format (data is not an array)');
            return [];
        }

        // Filter out any invalid conversations
        const validConversations = storageObj.data.filter(conv => {
            if (!conv || typeof conv !== 'object' || !conv.conversation_id) {
                console.warn('Found invalid conversation in storage, filtering out:', conv);
                return false;
            }
            return true;
        });

        console.log(`Loaded ${validConversations.length} valid conversations from storage (filtered out ${storageObj.data.length - validConversations.length} invalid items)`);

        return validConversations;
    } catch (e) {
        console.error('Error loading from localStorage:', e);
        return [];
    }
}

/**
 * Update a specific conversation in storage
 * @param {Object} conversation The conversation object to update
 * @returns {boolean} True if update was successful
 */
export function updateConversationInStorage(conversation) {
    if (!isLocalStorageAvailable()) {
        console.log('Local storage not available');
        return false;
    }

    if (!conversation || !conversation.conversation_id) {
        console.error('Invalid conversation data provided:', conversation);
        return false;
    }

    try {
        // Load existing conversations
        const conversations = loadConversationsFromStorage();

        // Check if this conversation already exists
        const index = conversations.findIndex(c => c.conversation_id === conversation.conversation_id);

        if (index >= 0) {
            // Improved history merging logic
            const existing = conversations[index];
            
            // For history, we need to ensure we preserve all messages
            let mergedHistory = [];
            
            if (Array.isArray(conversation.history) && conversation.history.length > 0) {
                // If new conversation has history, use it as base
                mergedHistory = [...conversation.history];
            } else if (Array.isArray(existing.history)) {
                // Otherwise keep existing history
                mergedHistory = [...existing.history];
            }
            
            // Update the conversation, keeping the merged history
            conversations[index] = {
                ...existing,          // Start with all existing fields
                ...conversation,      // Update with new data
                history: mergedHistory, // Use our carefully merged history
                last_updated: new Date().toISOString() // Add last updated timestamp
            };
            
            console.log(`Updated existing conversation in storage: ${conversation.conversation_id}`);
        } else {
            // Add new conversation with timestamp
            conversations.push({
                ...conversation,
                last_updated: new Date().toISOString()
            });
            console.log(`Added new conversation to storage: ${conversation.conversation_id}`);
        }

        // Save the updated list immediately
        return saveConversationsToStorage(conversations);
    } catch (e) {
        console.error('Error updating conversation in storage:', e);
        return false;
    }
}

