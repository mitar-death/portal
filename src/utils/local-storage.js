// Local storage utility for managing conversation data
import debounce from 'lodash/debounce';

// Constants
const STORAGE_KEY_PREFIX = 'tg_portal_';
const CONVERSATIONS_STORAGE_KEY = `${STORAGE_KEY_PREFIX}conversations`;
const MAX_ITEMS_TO_STORE = 500; // Maximum number of conversation items to store

const STORAGE_VERSION = '1.1'; // Version for future compatibility

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

            // Sort by last message time or last_updated time (newest first)
            validConversations.sort((a, b) => {
                // Try to get the last_message_time first, then fall back to last_updated
                const timeA = a.last_message_time ? new Date(a.last_message_time) :
                    (a.last_updated ? new Date(a.last_updated) : new Date(0));
                const timeB = b.last_message_time ? new Date(b.last_message_time) :
                    (b.last_updated ? new Date(b.last_updated) : new Date(0));
                return timeB - timeA;
            });

            // Keep only the most recent MAX_ITEMS_TO_STORE conversations
            storageObj.data = validConversations.slice(0, MAX_ITEMS_TO_STORE);
        }

        // Save to localStorage
        const json = JSON.stringify(storageObj);
        localStorage.setItem(CONVERSATIONS_STORAGE_KEY, json);

        return true;
    } catch (e) {
        console.error('Error saving to localStorage:', e);

        // For quota errors, try a more strategic cleanup approach
        if (e.name === 'QuotaExceededError' || e.code === 22) {
            console.warn('Storage quota exceeded. Attempting to free up space...');

            try {
                // Strategy 1: Trim history of all conversations to last 30 messages
                const trimmedConversations = conversations.map(conv => {
                    if (conv && conv.history && Array.isArray(conv.history) && conv.history.length > 30) {
                        return {
                            ...conv,
                            history: conv.history.slice(-30), // Keep only the 30 most recent messages
                            history_trimmed: true
                        };
                    }
                    return conv;
                });

                // Create a new storage object with trimmed data
                const trimmedObj = {
                    version: STORAGE_VERSION,
                    lastUpdated: new Date().toISOString(),
                    data: trimmedConversations
                };

                const trimmedJson = JSON.stringify(trimmedObj);
                localStorage.setItem(CONVERSATIONS_STORAGE_KEY, trimmedJson);
                return true;
            } catch (trimError) {
                console.warn('Failed to save with trimmed histories:', trimError);

                // Strategy 2: Keep only the 20 most recent conversations
                try {
                    // Sort by last updated or last message time
                    const sortedConversations = [...conversations].sort((a, b) => {
                        const timeA = a.last_message_time ? new Date(a.last_message_time) :
                            (a.last_updated ? new Date(a.last_updated) : new Date(0));
                        const timeB = b.last_message_time ? new Date(b.last_message_time) :
                            (b.last_updated ? new Date(b.last_updated) : new Date(0));
                        return timeB - timeA;
                    });

                    const recentObj = {
                        version: STORAGE_VERSION,
                        lastUpdated: new Date().toISOString(),
                        data: sortedConversations.slice(0, 20) // Keep 20 most recent
                    };

                    localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(recentObj));
                    return true;
                } catch (sortError) {
                    console.error('Failed to save recent conversations:', sortError);

                    // Last resort: Save only the most recently used conversation
                    try {
                        // Find most recent conversation if we can
                        let mostRecentConversation = null;
                        if (conversations.length > 0) {
                            // Try to find the most recently updated one
                            mostRecentConversation = conversations.reduce((latest, current) => {
                                const latestTime = latest.last_message_time ? new Date(latest.last_message_time) :
                                    (latest.last_updated ? new Date(latest.last_updated) : new Date(0));
                                const currentTime = current.last_message_time ? new Date(current.last_message_time) :
                                    (current.last_updated ? new Date(current.last_updated) : new Date(0));
                                return currentTime > latestTime ? current : latest;
                            }, conversations[0]);

                            // If we have history, trim it to absolute minimum
                            if (mostRecentConversation.history && mostRecentConversation.history.length > 10) {
                                mostRecentConversation = {
                                    ...mostRecentConversation,
                                    history: mostRecentConversation.history.slice(-10)
                                };
                            }
                        }

                        const emergencyObj = {
                            version: STORAGE_VERSION,
                            lastUpdated: new Date().toISOString(),
                            data: mostRecentConversation ? [mostRecentConversation] : []
                        };

                        localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(emergencyObj));
                        console.warn('Emergency storage: Saved only the most recent conversation with trimmed history');
                        return true;
                    } catch (finalError) {
                        // Absolute last resort: Clear everything
                        console.error('All attempts to save conversations failed. Clearing storage:', finalError);
                        try {
                            localStorage.removeItem(CONVERSATIONS_STORAGE_KEY);
                        } catch (clearError) {
                            console.error('Failed to clear localStorage:', clearError);
                        }
                        return false;
                    }
                }
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

        if (storageObj.version !== STORAGE_VERSION) {
            console.warn(`Storage version mismatch: ${storageObj.version} vs ${STORAGE_VERSION}`);
        }

        // Validate data format
        if (!storageObj.data) {
            console.warn('Invalid storage format (missing data property)');

            // Try to recover from a direct conversation array format
            if (Array.isArray(storageObj)) {
                return verifyConversationIntegrity(storageObj);
            }

            // Last attempt: check if the storage object itself might be a conversation
            if (storageObj.conversation_id) {
                return verifyConversationIntegrity([storageObj]);
            }

            return [];
        }

        if (!Array.isArray(storageObj.data)) {
            console.warn('Invalid storage format (data is not an array)');

            // Try one more recovery attempt - if data is an object with conversation_id
            if (storageObj.data && storageObj.data.conversation_id) {
                return verifyConversationIntegrity([storageObj.data]);
            }

            return [];
        }

        // Apply data integrity verification to ensure all conversations are valid
        const verifiedConversations = verifyConversationIntegrity(storageObj.data);

        // Check if we've lost a significant number of conversations - if so, try recovery
        if (storageObj.data.length > 0 && verifiedConversations.length === 0) {
            const recoveredConversations = attemptConversationRecovery();
            if (recoveredConversations.length > 0) {
                return recoveredConversations;
            }
        }

        return verifiedConversations;
    } catch (e) {
        console.error('Error loading from localStorage:', e);

        // Attempt recovery if JSON parsing fails
        console.warn('Attempting emergency conversation recovery after load failure');
        return attemptConversationRecovery();
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

/**
 * Debounced version of updateConversationInStorage to prevent excessive writes
 * Will wait 500ms before actually saving to reduce the chance of data loss during rapid updates
 */
export const debouncedUpdateConversation = debounce((conversation) => {
    return updateConversationInStorage(conversation);
}, 500, { maxWait: 2000 });

/**
 * Get a specific conversation by ID from storage
 * @param {string} conversationId The ID of the conversation to retrieve
 * @returns {Object|null} The conversation object or null if not found
 */
export function getConversationFromStorage(conversationId) {
    if (!conversationId) {
        console.error('No conversation ID provided');
        return null;
    }

    try {
        const conversations = loadConversationsFromStorage();
        const conversation = conversations.find(c => c.conversation_id === conversationId);

        if (!conversation) {
            console.log(`Conversation not found in storage: ${conversationId}`);
            return null;
        }

        return conversation;
    } catch (e) {
        console.error('Error retrieving conversation from storage:', e);
        return null;
    }
}

/**
 * Emergency recovery function to try to find any conversation data that might still be in localStorage
 * @returns {Array} Any recovered conversations or empty array
 */
export function attemptConversationRecovery() {
    if (!isLocalStorageAvailable()) {
        return [];
    }

    try {
        // Look for any keys that might contain conversation data
        const potentialKeys = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key.includes('conversation') || key.includes('chat') || key.includes('tg_portal')) {
                potentialKeys.push(key);
            }
        }

        // Try to extract conversation data from these keys
        const recoveredConversations = [];
        potentialKeys.forEach(key => {
            try {
                const data = JSON.parse(localStorage.getItem(key));

                // Check for conversation arrays
                if (data && data.data && Array.isArray(data.data)) {
                    data.data.forEach(item => {
                        if (item && item.conversation_id) {
                            recoveredConversations.push(item);
                        }
                    });
                }
                // Check if this is a direct conversation object
                else if (data && data.conversation_id) {
                    recoveredConversations.push(data);
                }
            } catch (e) {
                console.warn(`Failed to parse potential conversation data from key ${key}:`, e);
            }
        });
        ;

        // Remove duplicates based on conversation_id
        const uniqueRecovered = [];
        const seenIds = new Set();
        recoveredConversations.forEach(conv => {
            if (!seenIds.has(conv.conversation_id)) {
                seenIds.add(conv.conversation_id);
                uniqueRecovered.push(conv);
            }
        });

        return uniqueRecovered;
    } catch (e) {
        console.error('Error during conversation recovery attempt:', e);
        return [];
    }
}

/**
 * Verify the integrity of loaded conversation data
 * @param {Array} conversations Array of conversations to verify
 * @returns {Array} Verified and potentially repaired conversations
 */
export function verifyConversationIntegrity(conversations) {
    if (!Array.isArray(conversations)) {
        console.warn('Invalid conversations data provided for verification');
        return [];
    }

    try {
        // Repair and verify each conversation
        const verifiedConversations = conversations.map(conv => {
            // Skip if critically invalid
            if (!conv || typeof conv !== 'object' || !conv.conversation_id) {
                return null;
            }

            const verified = {
                ...conv,
                last_updated: conv.last_updated || conv.last_message_time || new Date().toISOString(),
                history: Array.isArray(conv.history) ? conv.history : []
            };

            if (verified.history.length > 0) {
                verified.history = verified.history.filter(msg => {
                    return msg && (msg.message || msg.text || msg.content);
                });

                verified.history.sort((a, b) => {
                    const timeA = a.timestamp ? new Date(a.timestamp) : new Date(0);
                    const timeB = b.timestamp ? new Date(b.timestamp) : new Date(0);
                    return timeA - timeB;
                });

                const uniqueMessages = [];
                const seenSignatures = new Set();

                verified.history.forEach(msg => {
                    const content = msg.message || msg.text || msg.content || '';
                    const timestamp = msg.timestamp || '';
                    const signature = `${content.substring(0, 50)}_${timestamp}`;

                    if (!seenSignatures.has(signature)) {
                        seenSignatures.add(signature);
                        uniqueMessages.push(msg);
                    }
                });

                verified.history = uniqueMessages;
            }

            return verified;
        }).filter(Boolean); // Remove any null items

        return verifiedConversations;
    } catch (e) {
        console.error('Error during conversation verification:', e);
        return conversations; // Return original in case of error
    }
}

