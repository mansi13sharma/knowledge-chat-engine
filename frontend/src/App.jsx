import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

// Whole-message (not substring) matches that signal the user is wrapping up
// the conversation, e.g. "thanks!" or "ok that's all bye" — used to trigger
// the end-of-chat feedback prompt.
const ENDING_PHRASES = [
  "bye", "goodbye", "good bye", "see you", "see ya", "cya",
  "thanks", "thank you", "thanks a lot", "thank you so much", "thank you very much",
  "thats all", "that is all", "no thanks", "nope thanks", "thats it",
  "nothing else", "no thats all", "im done", "all good", "ok thanks",
  "okay thanks", "ok thank you", "alright thanks", "thats all i needed",
  "thats everything",
];

function isConversationEnding(text) {
  const normalized = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return false;
  return ENDING_PHRASES.some(
    (phrase) =>
      normalized === phrase ||
      normalized.endsWith(` ${phrase}`) ||
      normalized.startsWith(`${phrase} `)
  );
}

// How long the chat can sit idle (no new user/bot messages) before the
// feedback prompt is shown automatically.
const INACTIVITY_MS = 90 * 1000;

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(true);
  // null | "asking" | "unsatisfied" | "ticketCreated"
  const [feedbackStage, setFeedbackStage] = useState(null);
  const [chatEnded, setChatEnded] = useState(false);
  const [creatingTicket, setCreatingTicket] = useState(false);
  const [ticketInfo, setTicketInfo] = useState(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [ratingSubmitted, setRatingSubmitted] = useState(false);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);
  const inactivityTimerRef = useRef(null);

  // Suggestions for empty state — real questions verified against the FAQ/KB content
  const suggestions = [
    { text: "How do I reset my password?", label: "Reset Password" },
    { text: "How does a Mentor Admin pair an entrepreneur with a mentor?", label: "Mentor Pairing" },
    { text: "How does an M&E Admin onboard a new enumerator?", label: "Enumerator Onboarding" },
    { text: "What is the difference between an External Reviewer and a QA reviewer?", label: "Reviewer vs QA" }
  ];

  // Auto-scroll to the bottom of the chat
  useEffect(() => {
    console.log("[Chat] Auto-scrolling to bottom. Message count:", messages.length);
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Check connection to backend on load
  useEffect(() => {
    console.log("[Connection] Checking backend connection status on load...");
    const checkConnection = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/health");
        if (res.ok) {
          console.log("[Connection] Backend is online and responding.");
          setIsConnected(true);
        } else {
          console.warn("[Connection] Backend returned non-OK status:", res.status);
          setIsConnected(false);
        }
      } catch (err) {
        console.error("[Connection] Failed to connect to backend:", err);
        setIsConnected(false);
      }
    };
    checkConnection();
  }, []);

  // Prompt for feedback after 1.5 minutes with no new user/bot message, as
  // long as the chat is actually underway and no feedback flow is already
  // in progress. Resets on every message and re-arms automatically because
  // this effect re-runs whenever `messages` changes.
  useEffect(() => {
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    if (chatEnded || feedbackStage || loading || messages.length === 0) {
      return;
    }
    inactivityTimerRef.current = setTimeout(() => {
      console.log("[Feedback] 1.5 minutes of inactivity — showing feedback prompt.");
      setFeedbackStage("asking");
    }, INACTIVITY_MS);
    return () => clearTimeout(inactivityTimerRef.current);
  }, [messages, loading, feedbackStage, chatEnded]);

  // Handle textarea autosize
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [message]);

  const handleSendMessage = async (textToSend) => {
    const text = textToSend || message;
    if (!text.trim()) {
      console.warn("[Chat] Attempted to send empty message. Aborting.");
      return;
    }
    if (loading) {
      console.warn("[Chat] System is currently loading another response. Aborting.");
      return;
    }
    if (chatEnded || feedbackStage) {
      console.warn("[Chat] Chat is ended or awaiting feedback response. Aborting send.");
      return;
    }

    console.log("[Chat] Preparing to send message:", text);

    // Add user message to history
    const userMsg = {
      id: Date.now(),
      text: text,
      isUser: true,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    console.log("[Chat] Appending user message to chat UI:", userMsg);
    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setMessage("");
    setLoading(true);

    try {
      const history = messages
        .filter((m) => !m.isError)
        .map((m) => ({ role: m.isUser ? "user" : "assistant", content: m.text }));

      const payload = {
        user_id: "test_user",
        message: text,
        history,
      };
      console.log("[Chat] Dispatching API request to http://127.0.0.1:8000/chat with payload:", payload);

      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        console.error("[Chat] API request failed with status:", response.status, response.statusText);
        throw new Error("Server error");
      }

      const data = await response.json();
      console.log("[Chat] API response successfully received:", data);

      const botMsg = {
        id: Date.now() + 1,
        text: data.answer,
        isUser: false,
        confidence: data.confidence,
        escalated: data.escalated,
        answeredBy: data.answered_by,
        supportEmail: data.support_email,
        supportPhone: data.support_phone,
        sources: data.sources,
        followupSuggestions: data.followup_suggestions,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      console.log("[Chat] Appending assistant response to chat UI:", botMsg);
      setMessages((prev) => [...prev, botMsg]);

      if (isConversationEnding(text)) {
        console.log("[Feedback] Conversation-ending phrase detected — will prompt for feedback.");
        setTimeout(() => setFeedbackStage("asking"), 600);
      }
    } catch (err) {
      console.error("[Chat] Error occurred during message processing:", err);
      const errorMsg = {
        id: Date.now() + 1,
        text: "Unable to connect to the backend server. Please make sure the backend is running.",
        isUser: false,
        isError: true,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      console.log("[Chat] Enter key pressed. Submitting message.");
      handleSendMessage();
    }
  };

  const clearChat = () => {
    console.log("[Chat] Requesting clear chat history.");
    if (window.confirm("Are you sure you want to clear your chat history?")) {
      console.log("[Chat] Chat history cleared.");
      setMessages([]);
      setFeedbackStage(null);
      setChatEnded(false);
      setTicketInfo(null);
      setRating(0);
      setComment("");
      setRatingSubmitted(false);
    } else {
      console.log("[Chat] Clear chat cancelled by user.");
    }
  };

  const handleFeedbackSatisfied = () => {
    console.log("[Feedback] User is satisfied. Ending chat.");
    setFeedbackStage(null);
    setChatEnded(true);
  };

  const handleFeedbackUnsatisfied = () => {
    console.log("[Feedback] User is not satisfied. Offering continue/ticket options.");
    setFeedbackStage("unsatisfied");
  };

  const handleContinueChat = () => {
    console.log("[Feedback] User chose to continue chatting.");
    setFeedbackStage(null);
  };

  const handleCreateTicket = async () => {
    console.log("[Feedback] User requested a support ticket after negative feedback.");
    setCreatingTicket(true);
    try {
      const lastUserMsg = [...messages].reverse().find((m) => m.isUser);
      const lastBotMsg = [...messages].reverse().find((m) => !m.isUser && !m.isError);

      const response = await fetch("http://127.0.0.1:8000/chat/feedback/ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "test_user",
          query: lastUserMsg?.text || "User reported dissatisfaction with the chatbot session.",
          draft_answer: lastBotMsg?.text || null,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to create support ticket");
      }

      const data = await response.json();
      console.log("[Feedback] Support ticket created:", data);
      setTicketInfo({ supportEmail: data.support_email, supportPhone: data.support_phone });
    } catch (err) {
      console.error("[Feedback] Error creating support ticket:", err);
      setTicketInfo({ error: true });
    } finally {
      setFeedbackStage("ticketCreated");
      setChatEnded(true);
      setCreatingTicket(false);
    }
  };

  const startNewChat = () => {
    console.log("[Chat] Starting a new chat session.");
    setMessages([]);
    setFeedbackStage(null);
    setChatEnded(false);
    setTicketInfo(null);
    setRating(0);
    setComment("");
    setRatingSubmitted(false);
  };

  const handleRating = (star) => {
    console.log("[Feedback] Star rating selected:", star);
    setRating(star);
  };

  const handleSubmitRating = () => {
    console.log("[Feedback] Rating submitted:", { rating, comment: comment.trim() || null });
    setRatingSubmitted(true);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-title-area">
          <div className="bot-avatar-main">🤖</div>
          <div className="header-text">
            <h1>TEF AI Assistant</h1>
            <div className="status-badge">
              <span className="status-dot" style={{ backgroundColor: isConnected ? "#2ec4b6" : "#e71d36" }} />
              {isConnected ? "Server Online" : "Server Offline"}
            </div>
          </div>
        </div>
        {messages.length > 0 && (
          <button className="clear-btn" onClick={clearChat} title="Clear history">
            <span>🗑️</span> Clear Chat
          </button>
        )}
      </header>

      {/* Main Chat Area */}
      <main className="chat-area">
        {messages.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-logo">🤖</div>
            <h2>Welcome to TEF Support</h2>
            <p className="welcome-desc">
              Ask any question about mentor creation, support ticket processing, or configuration settings.
              Our RAG-powered agent is here to help!
            </p>
            <div className="suggestions-title">Suggested questions:</div>
            <div className="suggestions-grid">
              {suggestions.map((s, index) => (
                <button
                  key={index}
                  className="suggestion-card"
                  onClick={() => handleSendMessage(s.text)}
                >
                  <span>{s.label}</span>
                  <p className="suggestion-desc">{s.text}</p>
                  <span className="suggestion-arrow">→</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={msg.id} className={`message-row ${msg.isUser ? "user-row" : "bot-row"}`}>
              <div className={`avatar ${msg.isUser ? "user-avatar" : "bot-avatar"}`}>
                {msg.isUser ? "👤" : "🤖"}
              </div>
              <div className="message-content">
                <div className={`message-bubble ${msg.isUser ? "user-bubble" : "bot-bubble"} ${msg.isError ? "error-bubble" : ""}`}>
                  {msg.isUser ? (
                    msg.text
                  ) : (
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.text}</ReactMarkdown>
                    </div>
                  )}

                  {/* Escalation warning */}
                  {!msg.isUser && msg.escalated && (
                    <div className="escalation-notice">
                      <span className="escalation-icon">⚠️</span>
                      <div>
                        <div className="escalation-title">Escalated to Support Ticket</div>
                        A support ticket has been created automatically for human review.
                        {(msg.supportEmail || msg.supportPhone) && (
                          <> Contact {msg.supportEmail}{msg.supportEmail && msg.supportPhone ? " or " : ""}{msg.supportPhone} for immediate help.</>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Low-confidence fallback: clickable follow-up suggestion chips */}
                  {!msg.isUser && msg.followupSuggestions?.length > 0 && (
                    <div className="followup-chips">
                      {msg.followupSuggestions.map((question, qIndex) => (
                        <button
                          key={qIndex}
                          type="button"
                          className="followup-chip"
                          disabled={loading || chatEnded || !!feedbackStage || index !== messages.length - 1}
                          onClick={() => handleSendMessage(question)}
                        >
                          {question}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Message Meta (time, layer & confidence) */}
                <div className="message-meta">
                  <span>{msg.time}</span>
                  {!msg.isUser && msg.answeredBy === "faq" && (
                    <span className="layer-pill">Answered from FAQ</span>
                  )}
                  {!msg.isUser && msg.answeredBy === "kb" && msg.confidence != null && (
                    <span className={`confidence-pill ${msg.confidence < 0.6 ? "low" : ""}`}>
                      Knowledge Base · Confidence: {Math.round(msg.confidence * 100)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}

        {/* End-of-chat feedback prompt: fired on an ending phrase or 1.5min inactivity */}
        {feedbackStage === "asking" && (
          <div className="message-row bot-row">
            <div className="avatar bot-avatar">🤖</div>
            <div className="feedback-card">
              <p>I hope I was able to help you. Has your query been resolved?</p>
              <div className="feedback-actions">
                <button className="feedback-btn feedback-btn-positive" onClick={handleFeedbackSatisfied}>
                  👍 Yes, all good
                </button>
                <button className="feedback-btn feedback-btn-negative" onClick={handleFeedbackUnsatisfied}>
                  👎 Not quite
                </button>
              </div>
            </div>
          </div>
        )}

        {feedbackStage === "unsatisfied" && (
          <div className="message-row bot-row">
            <div className="avatar bot-avatar">🤖</div>
            <div className="feedback-card">
              <p>Sorry about that. Would you like to keep chatting, or should I connect you with our support team?</p>
              <div className="feedback-actions">
                <button className="feedback-btn" onClick={handleContinueChat} disabled={creatingTicket}>
                  Continue Chat
                </button>
                <button className="feedback-btn feedback-btn-negative" onClick={handleCreateTicket} disabled={creatingTicket}>
                  {creatingTicket ? "Creating ticket..." : "Create Support Ticket"}
                </button>
              </div>
            </div>
          </div>
        )}

        {feedbackStage === "ticketCreated" && (
          <div className="message-row bot-row">
            <div className="avatar bot-avatar">🤖</div>
            <div className="feedback-card">
              {ticketInfo?.error ? (
                <p>Sorry, something went wrong creating your support ticket. Please try again shortly or reach out to our support team directly.</p>
              ) : (
                <p>
                  A support ticket has been created and our team will follow up with you shortly.
                  {(ticketInfo?.supportEmail || ticketInfo?.supportPhone) && (
                    <> You can also reach them directly at {ticketInfo.supportEmail}{ticketInfo.supportEmail && ticketInfo.supportPhone ? " or " : ""}{ticketInfo.supportPhone}.</>
                  )}
                </p>
              )}
            </div>
          </div>
        )}
        {chatEnded && (
          <div className="message-row bot-row">
            <div className="avatar bot-avatar">🤖</div>
            <div className="feedback-card">
              <p>Thank you for chatting with us.</p>

              {ratingSubmitted ? (
                <p className="feedback-subtext">We appreciate your feedback! 🙏</p>
              ) : (
                <>
                  <p className="feedback-subtext">
                    We'd appreciate your feedback. Please rate your experience.
                  </p>
                  <div className="star-rating">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        className={`star-btn ${star <= rating ? "star-btn-active" : ""}`}
                        onClick={() => handleRating(star)}
                        aria-label={`Rate ${star} star${star > 1 ? "s" : ""}`}
                      >
                        ⭐
                      </button>
                    ))}
                  </div>
                  <textarea
                    className="comment-input"
                    placeholder="Any comments? (optional)"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows="2"
                  />
                  <div className="feedback-actions">
                    <button
                      className="feedback-btn feedback-btn-positive"
                      onClick={handleSubmitRating}
                      disabled={!rating}
                    >
                      Submit Feedback
                    </button>
                  </div>
                </>
              )}

              <button className="new-chat-btn" onClick={startNewChat}>
                Start New Chat
              </button>
            </div>
          </div>
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="message-row bot-row">
            <div className="avatar bot-avatar">🤖</div>
            <div className="message-bubble bot-bubble">
              <div className="typing-container">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </main>

      {/* Footer / Input Area */}
      <footer className="app-footer">
        <div className="input-container">
          <textarea
            ref={textareaRef}
            className="chat-input"
            rows="1"
            placeholder={chatEnded ? "This chat has ended. Start a new chat to continue." : "Type your message here..."}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={loading || chatEnded || !!feedbackStage}
          />
          <button
            className="send-btn"
            onClick={() => handleSendMessage()}
            disabled={loading || !message.trim() || chatEnded || !!feedbackStage}
          >
            <span className="send-icon">▲</span>
          </button>
        </div>
        <div className="footer-info">
          TEF Chatbot answers queries using local FAQs and Knowledge Base documents.
        </div>
      </footer>
    </div>
  );
}

export default App;
