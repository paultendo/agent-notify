class AgentNotify < Formula
  desc "Cross-platform notifications for AI coding agents (Codex, Claude Code, Gemini CLI)"
  homepage "https://github.com/paultendo/agent-notify"
  url "https://github.com/paultendo/agent-notify/archive/refs/tags/v1.0.0.tar.gz"
  sha256 ""
  license "MIT"

  def install
    bin.install "agent-notify"
  end

  test do
    assert_match "agent-notify", shell_output("#{bin}/agent-notify --version")
  end
end
