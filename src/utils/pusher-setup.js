// Pusher setup and configuration
import Pusher from 'pusher-js';
import { ref } from 'vue';

// Enable Pusher logging for debugging
Pusher.logToConsole = process.env.NODE_ENV === 'development';

// Settings for Pusher - you should define these in your environment variables
const PUSHER_KEY = process.env.VUE_APP_PUSHER_KEY || '94b88e97813b26aeb8ec';
const PUSHER_CLUSTER = process.env.VUE_APP_PUSHER_CLUSTER || 'mt1';

export async function initPusher() {
    try {
        console.log("Initializing Pusher with key:", PUSHER_KEY, "cluster:", PUSHER_CLUSTER);

        // For public channels, we don't need auth configuration
        const pusher = new Pusher(PUSHER_KEY, {
            cluster: PUSHER_CLUSTER,
            // Enhanced error handling
            enabledTransports: ['ws', 'wss'],
            disabledTransports: ['sockjs', 'xhr_streaming', 'xhr_polling'],
            timeout: 15000, // Longer timeout for better reliability
            activityTimeout: 120000, // 2 minutes activity timeout
            pongTimeout: 30000, // 30 seconds pong timeout
            // No auth needed for public channels
        });

        // Add connection error monitoring
        pusher.connection.bind('error', function (err) {
            console.error('Pusher connection error:', err);
            if (err.error && err.error.data && err.error.data.code) {
                console.error(`Pusher error code: ${err.error.data.code}`);
            }
        });

        return pusher;
    } catch (error) {
        console.error("Failed to initialize Pusher:", error);
        return null;
    }
}

export function disconnectPusher(pusher) {
    if (pusher) {
        pusher.disconnect();
        console.log("Pusher disconnected");
    }
}


// Pusher settings
export const settings = {
    PUSHER_KEY: PUSHER_KEY,
    PUSHER_CLUSTER: PUSHER_CLUSTER
};
