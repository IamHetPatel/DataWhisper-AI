export const sendToN8n = async (webhookUrl, payload) => {
  try {
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`n8n webhook error! status: ${response.status}`);
    }

    // n8n webhooks can return text or JSON, handling safely
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
      return await response.json();
    } else {
      return await response.text();
    }
  } catch (error) {
    console.error("Error sending data to n8n:", error);
    throw error;
  }
};

export const fetchFromN8n = async (webhookUrl) => {
  try {
    const response = await fetch(webhookUrl, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`n8n webhook error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Error fetching data from n8n:", error);
    throw error;
  }
};

// Mock function to simulate n8n response for testing during building
export const mockN8nResponse = async (mockData, delay = 1000) => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(mockData);
    }, delay);
  });
};
