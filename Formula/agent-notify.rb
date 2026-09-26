class AgentNotify < Formula
  desc "Cross-platform notifications for AI coding agents (Codex, Claude Code, Gemini CLI)"
  homepage "https://github.com/paultendo/agent-notify"
  url "https://github.com/paultendo/agent-notify/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "a8592d5b18e4072f430e66a05e62752fdecc63eb307128813704b1085f42fc6b"
  license "AGPL-3.0-only"

  def install
    bin.install "agent-notify"
  end

  test do
    assert_match "agent-notify", shell_output("#{bin}/agent-notify --version")
  end
end
