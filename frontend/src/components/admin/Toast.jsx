function Toast({ type, message, onDismiss }) {
  return (
    <div className={`kb-toast kb-toast-${type}`} role="status">
      <span>{message}</span>
      <button type="button" className="kb-toast-close" onClick={onDismiss} aria-label="Dismiss notification">
        ×
      </button>
    </div>
  );
}

export default Toast;
