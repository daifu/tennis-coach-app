"use client";

interface Props {
  onConfirm: () => void;
  onClose: () => void;
}

export default function CameraGuideModal({ onConfirm, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl max-w-sm w-full shadow-xl p-6 space-y-5">
        <h2 className="text-xl font-bold text-gray-900">Camera placement tips</h2>
        <ul className="space-y-3 text-sm text-gray-700">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-green-500 font-bold">1.</span>
            <span><strong>Side-on view</strong> — position the camera perpendicular to your stroke direction</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-green-500 font-bold">2.</span>
            <span><strong>Hip height</strong> — keep the camera at approximately hip level</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-green-500 font-bold">3.</span>
            <span><strong>10–15 feet away</strong> — your full body should be visible in frame</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-green-500 font-bold">4.</span>
            <span><strong>Good lighting</strong> — avoid backlighting; court or indoor lighting works best</span>
          </li>
        </ul>
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-gray-300 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-xl bg-green-500 text-white text-sm font-medium hover:bg-green-600 transition-colors"
          >
            Got it — choose file
          </button>
        </div>
      </div>
    </div>
  );
}
