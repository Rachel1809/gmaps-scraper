import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, Download, Eye, Terminal, Activity, MapPin, Monitor } from 'lucide-react';

export default function App() {
  const [socket, setSocket] = useState(null);
  const [status, setStatus] = useState("IDLE");
  const [logs, setLogs] = useState([]);
  const [rows, setRows] = useState([]);
  const [keyword, setKeyword] = useState("");
  // State lưu keyword của lần chạy trước để so sánh Resume
  const [lastKeyword, setLastKeyword] = useState(""); 
  
  const [headless, setHeadless] = useState(true);
  const [liveImage, setLiveImage] = useState(null);
  const [viewMode, setViewMode] = useState("live");
  const [exportFormat, setExportFormat] = useState("xlsx");
  
  const [columns, setColumns] = useState({
    name: true, address: true, phone: true, website: true, rating: true, link: true
  });
  const [showColMenu, setShowColMenu] = useState(false);
  const logsEndRef = useRef(null);

  // === DYNAMIC LOAD SHEETJS (XLSX) ===
  useEffect(() => {
    const script = document.createElement('script');
    script.src = "https://cdn.sheetjs.com/xlsx-0.19.3/package/dist/xlsx.full.min.js";
    script.async = true;
    document.body.appendChild(script);
    return () => {
      document.body.removeChild(script);
    }
  }, []);

  useEffect(() => {
    let targetUrl = 'ws://127.0.0.1:8000/ws'; 

    if (window.location.host.includes("ngrok")) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        targetUrl = `${protocol}//${window.location.host}/ws`;
    }

    console.log("Connecting to:", targetUrl);
    const ws = new WebSocket(targetUrl);

    ws.onopen = () => {
      addLog("> Connected to Scraper Engine.");
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "log") addLog(msg.payload);
      if (msg.type === "row") addRow(msg.payload);
      if (msg.type === "status") setStatus(msg.payload);
      if (msg.type === "image") setLiveImage(msg.payload);
    };

    ws.onclose = () => {
      addLog("> Disconnected from Engine.");
      setStatus("OFFLINE");
    };

    setSocket(ws);
    return () => ws.close();
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const addLog = (msg) => setLogs(prev => [...prev.slice(-99), msg]);
  
  const addRow = (row) => setRows(prev => [...prev, row]);

  const toggleScrape = () => {
    if (!socket) return;
    
    // Nút START được nhấn (khi đang IDLE hoặc STOPPED)
    if (status === "IDLE" || status === "STOPPED") {
      if (!keyword.trim()) {
        addLog("> Error: Keyword required.");
        return;
      }
      
      const currentKey = keyword.trim();
      let ignoreUrls = [];

      // === LOGIC RESUME vs NEW SESSION ===
      // Nếu keyword MỚI khác với keyword CŨ -> Xóa dữ liệu cũ, chạy mới
      if (currentKey !== lastKeyword) {
          setRows([]);
          setLogs([]);
          setLiveImage(null);
          setLastKeyword(currentKey); // Cập nhật keyword hiện tại làm mốc
          addLog(`> Starting NEW session for: "${currentKey}"`);
      } else {
          // Nếu keyword GIỐNG nhau -> Giữ nguyên rows, LẤY DANH SÁCH URL ĐÃ CÓ
          // Lọc ra các link hợp lệ để gửi xuống server
          ignoreUrls = rows.map(r => r.link).filter(l => l && l !== "N/A");
          addLog(`> RESUMING session for: "${currentKey}"`);
          addLog(`> Sending ${ignoreUrls.length} existing links to skip.`);
      }

      socket.send(JSON.stringify({ 
        action: "start", 
        keyword: currentKey, 
        headless, 
        ignore_urls: ignoreUrls // Gửi danh sách này xuống
      }));
    } 
    // Nút STOP được nhấn
    else {
      socket.send(JSON.stringify({ action: "stop" }));
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      toggleScrape();
    }
  };

  const toggleColumn = (col) => setColumns(prev => ({ ...prev, [col]: !prev[col] }));
  
  const exportData = () => {
    if (rows.length === 0) {
        alert("No data to export!");
        return;
    }

    const activeCols = Object.keys(columns).filter(k => columns[k]);
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);

    if (exportFormat === "xlsx") {
      if (!window.XLSX) {
        alert("Export library loading... Try again in 2s.");
        return;
      }

      const filteredRows = rows.map(row => {
        const newRow = {};
        activeCols.forEach(col => {
            newRow[col.toUpperCase()] = row[col];
        });
        return newRow;
      });

      const worksheet = window.XLSX.utils.json_to_sheet(filteredRows);
      const workbook = window.XLSX.utils.book_new();
      window.XLSX.utils.book_append_sheet(workbook, worksheet, "Data");
      
      // Auto-width adjustment
      const wscols = activeCols.map(() => ({ wch: 20 }));
      worksheet['!cols'] = wscols;

      window.XLSX.writeFile(workbook, `gmaps_export_${timestamp}.xlsx`);
      
    } else {
      const headers = activeCols.map(k => k.toUpperCase());
      const csvRows = rows.map(row => {
          return activeCols.map(col => {
              let val = row[col] || "";
              val = val.toString().replace(/"/g, '""'); 
              return `"${val}"`;
          }).join(",");
      });

      const csvContent = [headers.join(","), ...csvRows].join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `gmaps_export_${timestamp}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <div className="bg-[#2E3440] text-[#D8DEE9] font-mono h-screen flex flex-col overflow-hidden">
      <header className="bg-[#3B4252] p-3 md:p-4 shadow-lg border-b border-[#4C566A] flex flex-col md:flex-row md:items-center justify-between shrink-0 z-50 gap-3">
        <div className="flex items-center gap-3">
          <MapPin className="text-[#88C0D0]" size={24} />
          <div>
            <h1 className="text-lg md:text-xl font-bold tracking-wider text-[#88C0D0] leading-none">G-MAPS PRO</h1>
            <span className="text-[10px] md:text-xs text-gray-500 font-bold hidden sm:inline">RESILIENT EDITION</span>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-2 bg-[#2E3440] p-1 rounded-md border border-[#4C566A] shadow-inner w-full md:w-auto">
          <input 
            type="text" 
            placeholder="e.g. Gyms in Hanoi" 
            value={keyword} 
            onChange={(e) => setKeyword(e.target.value)} 
            onKeyDown={handleKeyDown}
            disabled={status === "RUNNING"} 
            className="bg-transparent text-white px-3 py-1 focus:outline-none w-full md:w-64 placeholder-gray-500 text-sm" 
          />
          <button onClick={toggleScrape} className={`w-full md:w-auto font-bold px-4 py-1.5 rounded shadow-sm transform active:scale-95 transition-all text-sm flex items-center justify-center gap-2 whitespace-nowrap ${status === "RUNNING" ? "bg-[#BF616A] text-white hover:bg-[#a6545c]" : "bg-[#A3BE8C] text-[#2E3440] hover:bg-[#97b483]"}`}>
            {status === "RUNNING" ? <><Square size={14} fill="currentColor" /> STOP</> : <><Play size={14} fill="currentColor" /> START</>}
          </button>
        </div>
        <div className="hidden md:flex items-center gap-4">
          <label className="flex items-center gap-2 text-xs text-[#EBCB8B] cursor-pointer hover:opacity-80 p-2 rounded border border-[#4C566A] bg-[#2E3440]">
            <input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} className="accent-[#EBCB8B]" /> Headless
          </label>
        </div>
      </header>
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
        
        {/* LEFT PANE: 1/4 Width */}
        <section className="w-full h-48 md:h-auto md:w-1/4 bg-[#1d1f21] border-b md:border-b-0 md:border-r border-[#4C566A] flex flex-col min-w-0 md:min-w-[250px] shrink-0">
          <div className="text-xs text-gray-400 p-2 uppercase tracking-widest font-bold bg-[#292e39] border-b border-[#4C566A] flex justify-between items-center shrink-0">
            <div className="flex gap-2">
               <button 
                 onClick={() => setViewMode("logs")}
                 className={`flex items-center gap-1 hover:text-white transition-colors ${viewMode === "logs" ? "text-[#88C0D0]" : "text-gray-500"}`}
               >
                 <Terminal size={12}/>
               </button>
               <button 
                 onClick={() => setViewMode("live")}
                 className={`flex items-center gap-1 hover:text-white transition-colors ${viewMode === "live" ? "text-[#88C0D0]" : "text-gray-500"}`}
               >
                 <Monitor size={12}/>
               </button>
            </div>
            <Activity size={12} className={status === "RUNNING" ? "text-green-400 animate-pulse" : "text-gray-600"} />
          </div>
          
          <div className="flex-1 overflow-y-auto font-mono text-xs p-3 space-y-1.5 text-[#A3BE8C] relative bg-[#1d1f21]">
            {viewMode === "logs" ? (
                <>
                  {logs.map((log, i) => <div key={i} className="border-l-2 border-transparent pl-1 opacity-90">{log}</div>)}
                  <div ref={logsEndRef} />
                </>
            ) : (
                // === UI FIX: CENTERED ITEM + LEFT FOCUSED ZOOM ===
                // justify-center: Căn giữa item (hình ảnh) trong khung đen
                // items-center: Căn giữa theo chiều dọc
                <div className="flex items-center justify-center h-full w-full overflow-hidden bg-black/50 relative">
                    {liveImage ? (
                        <img 
                            src={`data:image/png;base64,${liveImage}`} 
                            alt="Live View" 
                            className="max-w-none border border-[#4C566A] shadow-md transition-transform duration-200"
                            style={{ 
                                transform: "scale(0.7) translateX(7%)", // Zoom out và dịch chuyển sang trái
                                // "left center": Neo trọng tâm vào mép trái để thấy sidebar
                                transformOrigin: "right center" 
                            }}
                        />
                    ) : (
                        <div className="text-gray-600 text-center w-full">
                            <Monitor size={32} className="mx-auto mb-2 opacity-20"/>
                            <p>No Signal</p>
                        </div>
                    )}
                </div>
            )}
          </div>
        </section>

        {/* RIGHT PANE: 3/4 Width */}
        <section className="w-full md:w-3/4 bg-[#2E3440] flex flex-col relative min-h-0">
          <div className="text-xs text-gray-500 p-2 uppercase tracking-widest font-bold bg-[#2E3440] border-b border-[#4C566A] flex flex-wrap justify-between items-center shadow-md z-40 shrink-0 gap-2">
            <div className="flex items-center gap-2 relative">
              <span className="hidden sm:inline">Live Data</span>
              <button onClick={() => setShowColMenu(!showColMenu)} className="flex items-center gap-1 bg-[#4C566A] hover:bg-[#5E81AC] text-white px-2 sm:px-3 py-1 rounded transition-colors shadow-sm ml-2"><Eye size={12}/> Cols ▾</button>
              {showColMenu && (
                <div className="absolute top-full left-0 mt-2 bg-[#2E3440] border border-[#4C566A] rounded shadow-2xl p-2 z-50 w-40 flex flex-col gap-1 ring-1 ring-black ring-opacity-50">
                  {Object.keys(columns).map(col => <label key={col} className="flex items-center gap-2 cursor-pointer hover:bg-[#3B4252] p-1 rounded text-gray-300 capitalize"><input type="checkbox" checked={columns[col]} onChange={() => toggleColumn(col)} className="accent-[#88C0D0]" /> {col}</label>)}
                </div>
              )}
            </div>
            <div className="flex items-center gap-3"><span className="bg-[#88C0D0] text-[#2E3440] px-2 py-0.5 rounded text-[10px] font-bold">Rows: {rows.length}</span></div>
          </div>
          <div className="flex-1 overflow-auto bg-[#2E3440]" onClick={() => setShowColMenu(false)}>
            {/* TABLE FIXED LAYOUT */}
            <table className="w-full text-left border-collapse table-fixed">
              <thead className="sticky top-0 z-20 bg-[#3B4252] shadow-sm">
                <tr className="text-[#D8DEE9] text-xs sm:text-sm uppercase font-bold tracking-wider">
                  {columns.name && <th className="p-2 sm:p-3 w-[25%] border-b border-[#4C566A]">Name</th>}
                  {columns.address && <th className="p-2 sm:p-3 w-[25%] border-b border-[#4C566A]">Address</th>}
                  {columns.phone && <th className="p-2 sm:p-3 w-[22%] border-b border-[#4C566A]">Phone</th>}
                  {columns.website && <th className="p-2 sm:p-3 w-[8%] border-b border-[#4C566A] text-center">Web</th>}
                  {columns.rating && <th className="p-2 sm:p-3 w-[10%] border-b border-[#4C566A] text-center">Rate</th>}
                  {columns.link && <th className="p-2 sm:p-3 w-[10%] border-b border-[#4C566A] text-center">Link</th>}
                  <th className="w-auto border-b border-[#4C566A]"></th>
                </tr>
              </thead>
              <tbody className="text-[10px] sm:text-sm text-gray-300 divide-y divide-[#4C566A]">
                {rows.length === 0 && <tr className="h-64"><td colSpan="6" className="text-center text-gray-500 text-lg align-middle">Ready to Scrape</td></tr>}
                {rows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-[#3B4252] transition-colors group align-top">
                    {columns.name && <td className="p-2 sm:p-3 text-[#EBCB8B] font-medium break-words whitespace-normal">{row.name}</td>}
                    {columns.address && <td className="p-2 sm:p-3 text-gray-400 break-words whitespace-normal">{row.address}</td>}
                    {columns.phone && <td className="p-2 sm:p-3 text-[#88C0D0] font-mono break-all whitespace-normal">{row.phone}</td>}
                    
                    {columns.website && (
                      <td 
                        className={`p-2 sm:p-3 text-center break-all whitespace-normal transition-colors ${row.website && row.website !== "N/A" ? "text-blue-400 cursor-pointer hover:bg-[#4C566A] hover:text-blue-300" : "text-gray-500"}`}
                        onClick={() => {
                            if (row.website && row.website !== "N/A") {
                                const url = row.website.startsWith('http') ? row.website : `https://${row.website}`;
                                window.open(url, '_blank');
                            }
                        }}
                      >
                        🌐
                      </td>
                    )}

                    {columns.rating && <td className="p-2 sm:p-3 text-yellow-500 font-bold text-center">{row.rating}</td>}
                    
                    {columns.link && (
                      <td 
                        className="p-2 sm:p-3 text-center cursor-pointer hover:bg-[#4C566A] hover:text-white transition-colors"
                        onClick={() => row.link && window.open(row.link, '_blank')}
                      >
                        🔗
                      </td>
                    )}
                    <td></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
      <footer className="bg-[#3B4252] p-2 md:p-3 border-t border-[#4C566A] shrink-0 flex flex-col md:flex-row items-center justify-between z-30 gap-2 md:gap-0">
        <div className="text-xs sm:text-sm flex items-center gap-2 w-full md:w-auto justify-center md:justify-start">
          <span className="text-gray-400">Status:</span>
          <span className={`font-bold tracking-wide ${status === "RUNNING" ? "text-[#A3BE8C]" : "text-[#EBCB8B]"}`}>{status}</span>
        </div>
        
        {/* EXPORT SECTION */}
        <div className="flex items-center gap-4">
          <div className="flex items-center bg-[#2E3440] rounded px-2 py-1 border border-[#4C566A]">
             <label className="flex items-center gap-1 text-[10px] sm:text-xs text-gray-300 cursor-pointer hover:text-white mr-2">
                <input 
                    type="radio" 
                    name="format" 
                    checked={exportFormat === "xlsx"} 
                    onChange={() => setExportFormat("xlsx")}
                    className="accent-[#88C0D0]" 
                /> 
                .xlsx
             </label>
             <label className="flex items-center gap-1 text-[10px] sm:text-xs text-gray-300 cursor-pointer hover:text-white">
                <input 
                    type="radio" 
                    name="format" 
                    checked={exportFormat === "csv"} 
                    onChange={() => setExportFormat("csv")}
                    className="accent-[#88C0D0]" 
                /> 
                .csv
             </label>
          </div>

          <button onClick={exportData} className="bg-[#5E81AC] hover:bg-[#81A1C1] text-white font-bold px-4 py-1 rounded shadow-sm text-[10px] sm:text-sm flex items-center gap-2 h-8 md:h-9 transition-colors">
            <Download size={14}/> EXPORT
          </button>
        </div>
      </footer>
    </div>
  );
}