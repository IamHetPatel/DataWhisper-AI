import { useState, useEffect } from "react";
import { mockN8nResponse } from "../lib/n8n";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulating fetching data from an n8n workflow
    const loadMockData = async () => {
      setLoading(true);
      const res = await mockN8nResponse({ message: "Welcome to the base app!", status: "Connected" });
      setData(res);
      setLoading(false);
    };
    
    loadMockData();
  }, []);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-100">Overview Dashboard</h2>
      
      {/* 
        This is where you drop Lovable-generated React Components!
        They will automatically inherit the Tailwind styling and spacing.
      */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* Placeholder Widget 1 */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-medium text-gray-600 dark:text-gray-300 mb-2">System Status</h3>
          {loading ? (
             <div className="animate-pulse flex space-x-4">
              <div className="flex-1 space-y-4 py-1">
                <div className="h-4 bg-gray-200 dark:bg-gray-600 rounded w-3/4"></div>
                <div className="h-4 bg-gray-200 dark:bg-gray-600 rounded"></div>
              </div>
            </div>
          ) : (
            <div>
              <p className="text-2xl font-bold text-green-500">{data?.status || 'Unknown'}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">{data?.message}</p>
            </div>
          )}
        </div>

        {/* Placeholder Widget 2 */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 flex flex-col items-center justify-center min-h-[160px] border-dashed border-2">
           <p className="text-gray-400 text-sm text-center">Drop a Lovable Chart Component Here</p>
        </div>

        {/* Placeholder Widget 3 */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 flex flex-col items-center justify-center min-h-[160px] border-dashed border-2">
           <p className="text-gray-400 text-sm text-center">Drop an n8n Trigger Form Here</p>
        </div>

      </div>
    </div>
  );
}
