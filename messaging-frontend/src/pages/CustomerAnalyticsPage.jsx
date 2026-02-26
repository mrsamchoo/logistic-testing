import { useState, useEffect } from 'react';
import { api } from '../api/client';

// Simple bar chart component
function BarChart({ data, maxVal, labelKey, valueKey, color = 'bg-blue-500' }) {
  if (!data || data.length === 0) return <p className="text-sm text-gray-400">ยังไม่มีข้อมูล</p>;
  const max = maxVal || Math.max(...data.map((d) => d[valueKey] || 0), 1);
  return (
    <div className="space-y-1.5">
      {data.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs text-gray-500 w-16 text-right shrink-0">{item[labelKey]}</span>
          <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
            <div
              className={`${color} h-5 rounded-full transition-all duration-500 flex items-center justify-end pr-2`}
              style={{ width: `${Math.max((item[valueKey] / max) * 100, 2)}%` }}
            >
              {item[valueKey] > 0 && <span className="text-xs text-white font-medium">{item[valueKey]}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function HourlyChart({ hourlyData }) {
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxCount = Math.max(...hours.map((h) => hourlyData[String(h)] || 0), 1);

  return (
    <div className="flex items-end gap-0.5 h-40">
      {hours.map((h) => {
        const count = hourlyData[String(h)] || 0;
        const height = count > 0 ? Math.max((count / maxCount) * 100, 5) : 2;
        const isActive = h >= 8 && h <= 20;
        return (
          <div key={h} className="flex-1 flex flex-col items-center gap-1 group relative">
            <div
              className={`w-full rounded-t transition-all ${isActive ? 'bg-blue-500 hover:bg-blue-600' : 'bg-gray-300 hover:bg-gray-400'}`}
              style={{ height: `${height}%` }}
              title={`${String(h).padStart(2, '0')}:00 — ${count} ข้อความ`}
            />
            {h % 3 === 0 && (
              <span className="text-[10px] text-gray-400">{String(h).padStart(2, '0')}</span>
            )}
            {/* Tooltip */}
            <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
              {String(h).padStart(2, '0')}:00 — {count}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function CustomerAnalyticsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/analytics/customer-behavior')
      .then(setData)
      .catch((e) => console.error('Analytics error:', e))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!data) {
    return <div className="p-6 text-gray-500">ไม่สามารถโหลดข้อมูลได้</div>;
  }

  // Format response time
  const avgSeconds = data.avg_response_time_seconds || 0;
  let responseTimeText = '';
  if (avgSeconds < 60) {
    responseTimeText = `${Math.round(avgSeconds)} วินาที`;
  } else if (avgSeconds < 3600) {
    responseTimeText = `${Math.round(avgSeconds / 60)} นาที`;
  } else {
    responseTimeText = `${(avgSeconds / 3600).toFixed(1)} ชั่วโมง`;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">📊 พฤติกรรมลูกค้า</h1>
        <span className="text-sm text-gray-400">Customer Behavior Analytics</span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <p className="text-sm text-gray-500">เวลาตอบกลับเฉลี่ย</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">{responseTimeText || 'N/A'}</p>
          <p className="text-xs text-gray-400 mt-1">Admin + AI Response Time</p>
        </div>
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <p className="text-sm text-gray-500">ลูกค้าที่ active สูงสุด</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {data.top_contacts?.[0]?.display_name || data.top_contacts?.[0]?.platform_user_id || 'N/A'}
          </p>
          <p className="text-xs text-gray-400 mt-1">{data.top_contacts?.[0]?.message_count || 0} ข้อความ</p>
        </div>
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <p className="text-sm text-gray-500">หมวดสินค้ายอดนิยม</p>
          <p className="text-2xl font-bold text-purple-600 mt-1">
            {Object.entries(data.product_categories || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || 'ยังไม่มีข้อมูล'}
          </p>
          <p className="text-xs text-gray-400 mt-1">จากการวิเคราะห์ keyword ในแชท</p>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Hourly Activity */}
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-3">⏰ ช่วงเวลาที่ลูกค้าทักบ่อย</h2>
          <p className="text-xs text-gray-400 mb-3">จำนวนข้อความตามชั่วโมง (24 ชม.)</p>
          <HourlyChart hourlyData={data.hourly_activity || {}} />
        </div>

        {/* Daily Activity */}
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-3">📅 วันที่ลูกค้าทักบ่อย</h2>
          <p className="text-xs text-gray-400 mb-3">จำนวนข้อความตามวันในสัปดาห์</p>
          <BarChart
            data={data.daily_activity || []}
            labelKey="day"
            valueKey="count"
            color="bg-indigo-500"
          />
        </div>

        {/* Product Categories */}
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-3">📦 หมวดหมู่สินค้าที่ลูกค้าสนใจ</h2>
          <p className="text-xs text-gray-400 mb-3">วิเคราะห์จาก keyword ใน 500 ข้อความล่าสุด</p>
          {Object.keys(data.product_categories || {}).length > 0 ? (
            <BarChart
              data={Object.entries(data.product_categories).map(([cat, count]) => ({ name: cat, count })).sort((a, b) => b.count - a.count)}
              labelKey="name"
              valueKey="count"
              color="bg-emerald-500"
            />
          ) : (
            <div className="text-center py-8 text-gray-400">
              <p className="text-4xl mb-2">📭</p>
              <p className="text-sm">ยังไม่พบ keyword สินค้าในข้อความ</p>
              <p className="text-xs mt-1">ระบบจะวิเคราะห์อัตโนมัติเมื่อมีข้อความจากลูกค้า</p>
            </div>
          )}
        </div>

        {/* Monthly Trend */}
        <div className="bg-white rounded-xl p-5 border shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-3">📈 แนวโน้มข้อความรายเดือน</h2>
          <p className="text-xs text-gray-400 mb-3">จำนวนข้อความจากลูกค้าย้อนหลัง 12 เดือน</p>
          <BarChart
            data={data.monthly_trend || []}
            labelKey="month"
            valueKey="count"
            color="bg-sky-500"
          />
        </div>
      </div>

      {/* Top Contacts Table */}
      <div className="bg-white rounded-xl p-5 border shadow-sm">
        <h2 className="font-semibold text-gray-700 mb-3">🏆 ลูกค้าที่ Active สูงสุด (Top 20)</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b text-gray-500">
                <th className="py-2 pr-3">#</th>
                <th className="py-2 pr-3">ชื่อ</th>
                <th className="py-2 pr-3">รหัสลูกค้า</th>
                <th className="py-2 pr-3 text-center">จำนวนข้อความ</th>
                <th className="py-2 pr-3">เข้าใช้ครั้งแรก</th>
                <th className="py-2 pr-3">ล่าสุด</th>
                <th className="py-2">หมายเหตุ</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_contacts || []).map((contact, i) => (
                <tr key={contact.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="py-2 pr-3 text-gray-400">{i + 1}</td>
                  <td className="py-2 pr-3 font-medium">{contact.display_name || contact.platform_user_id}</td>
                  <td className="py-2 pr-3">
                    {contact.customer_code ? (
                      <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded">{contact.customer_code}</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-center">
                    <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-0.5 rounded-full">
                      {contact.message_count}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-gray-500 text-xs">{contact.first_seen_at ? new Date(contact.first_seen_at).toLocaleDateString('th-TH') : '-'}</td>
                  <td className="py-2 pr-3 text-gray-500 text-xs">{contact.last_message_at ? new Date(contact.last_message_at).toLocaleDateString('th-TH') : '-'}</td>
                  <td className="py-2 text-gray-400 text-xs max-w-[200px] truncate">{contact.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!data.top_contacts || data.top_contacts.length === 0) && (
            <p className="text-center py-6 text-gray-400 text-sm">ยังไม่มีข้อมูลลูกค้า</p>
          )}
        </div>
      </div>
    </div>
  );
}
