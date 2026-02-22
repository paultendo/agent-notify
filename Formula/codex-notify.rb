class CodexNotify < Formula
  desc "macOS notifications for OpenAI Codex with reliable VSCode activation"
  homepage "https://github.com/paultendo/codex-notify"
  url "https://github.com/paultendo/codex-notify/archive/refs/tags/v0.6.0.tar.gz"
  sha256 ""
  license "MIT"

  depends_on :macos

  def install
    bin.install "codex-notify"
  end

  test do
    assert_match "codex-notify", shell_output("#{bin}/codex-notify --version")
  end
end
