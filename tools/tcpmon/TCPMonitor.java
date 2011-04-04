import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.net.UnknownHostException;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

/**
 * <p>TCP监视器，它在本地监听端口，将请求转发到远端服务器，并将请求返回。</p>
 * 
 * <p><code>java TCPMonitor －a :8080 localhost:8000</code><br> 监听本地的8080端口，将请求转发给本机的8000端口，并将所有请求响应输出到标准错误输出。</p>
 * 
 * <p><code>java TCPMonitor :8080 cloak:22</code><br> 监听本地的8080端口，并将请求转发给cloak主机的22端口</p>
 * 
 * @author marlonyao<yaolei135@gmail.com>
 */
class TCPMonitor {
	public static void main (String[] args) throws IOException {
		Options options = null;
		try {
			options = parseArgs(args);
			if (options.help) {
				usage();
				System.exit(0);
			}
		} catch (Exception e) {
			usage();
			System.exit(-1);
		}

		ServerSocket serverSocket = new ServerSocket();
		serverSocket.setReuseAddress(true);
		serverSocket.bind(new InetSocketAddress(options.host, options.port));
		System.out.println("server started on " + serverSocket.getInetAddress() + ":" + serverSocket.getLocalPort());
		Executor executor = Executors.newFixedThreadPool(options.threadCount);
		while(true) {
			Socket sock = serverSocket.accept();
			System.out.println("accept connection: " + sock.getInetAddress());
			executor.execute(new MonitorThread(sock, options.remoteHost, options.remotePort, options.dumpRequest, options.dumpResponse));
		}
	}

	static class Options {
		boolean help;
		boolean dumpRequest;
		boolean dumpResponse;
		int threadCount = 10;

		String host = "localhost";
		int port;
		String remoteHost;
		int remotePort;
	}

	private static void usage() {
		System.err.print(
				"java TCPMonitor [options] [host]:port remote_host:remote_port\n" +
				"        -h, --help             print this help\n" +
				"        -r, --dump-request     dump request to stderr\n" +
				"        -s, --dump-response    dump response to stderr\n" +
				"        -a, --dump-all         dump request and response to stderr\n" +
				"        -n, --threads=N        thread count, default is 10\n");
	}

	private static Options parseArgs(String[] args) {
		Options options = new Options();
		int i;
		// parse options
		for (i = 0; i < args.length; i++) {
			if (!args[i].startsWith("-")) {
				break;
			}
			if (args[i].equals("-h") || args[i].equals("--help")) {
				options.help = true;
			} else if (args[i].equals("-r") || args[i].equals("--dump-request")) {
				options.dumpRequest = true;
			} else if (args[i].equals("-s") || args[i].equals("--dump-response")) {
				options.dumpResponse = true;
			} else if (args[i].equals("-a") || args[i].equals("--dump-all")) {
				options.dumpRequest = true;
				options.dumpResponse = true;
			} else if (args[i].equals("-n") || args[i].startsWith("--threads=")) {
				if (args[i].equals("-n")) {
					options.threadCount = Integer.parseInt(args[++i]);
				} else {
					options.threadCount = Integer.parseInt(args[i].substring("--threads=".length()));
				}
			}
		}
		// parse remainder
		String localPart = args[i++];
		String[] bits = localPart.split(":");
		if (bits[0].length() > 0) {
			options.host = bits[0];
		}
		options.port = Integer.parseInt(bits[1]);

		String remotePart = args[i++];
		bits = remotePart.split(":");
		options.remoteHost = bits[0];
		options.remotePort = Integer.parseInt(bits[1]);

		return options;
	}
}

class MonitorThread implements Runnable {
	static final int BUFLEN = 1024;
	static final byte[] EOF = new byte[0];		// flag the end of channel 

	Socket lsock;
	String rhost;
	int rport;
	boolean dumpRequest;
	boolean dumpResponse;

	Socket rsock;
	BlockingQueue<byte[]> lrchannel;			// channel between read lsock and write rsock
	BlockingQueue<byte[]> rlchannel;			// channel between read rsock and write lsock

	volatile boolean shutdownRequested;
	Thread readLSockThread;
	Thread writeRSockThread;
	Thread readRSockThread;
	Thread writeLSockThread;

	public MonitorThread(Socket sock, String remoteHost, int remotePort, boolean dumpRequest, boolean dumpResponse) {
		this.lsock = sock;
		this.rhost = remoteHost;
		this.rport = remotePort;
		this.dumpRequest = dumpRequest;
		this.dumpResponse = dumpResponse;
	}

	public void run() {
		try {
			rsock = new Socket(rhost, rport);
		} catch (UnknownHostException e) {
			System.out.println("unknown host: " + rhost);
			return;
		} catch (IOException e) {
			System.out.println(e);
			return;
		}

		try {
			lrchannel = new ArrayBlockingQueue<byte[]>(10);
			rlchannel = new ArrayBlockingQueue<byte[]>(10);

			readLSockThread = new Thread(new ReadLSockThread());
			readLSockThread.start();
			writeRSockThread = new Thread(new WriteRSockThread());
			writeRSockThread.start();
			readRSockThread = new Thread(new ReadRSockThread());
			readRSockThread.start();
			writeLSockThread = new Thread(new WriteLSockThread());
			writeLSockThread.start();

			readLSockThread.join();
			writeRSockThread.join();
			readRSockThread.join();
			writeLSockThread.join();
			System.out.println("connection closed: " + lsock.getInetAddress());
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
		}
	}

	// close all socks and stop all threads
	private void shutdown() {
		try {
			if (shutdownRequested)
				return;
			shutdownRequested = true;
			if (!lsock.isClosed())
				lsock.close();
			if (!rsock.isClosed())
				rsock.close();
			readLSockThread.interrupt();
			writeRSockThread.interrupt();
			readRSockThread.interrupt();
			writeLSockThread.interrupt();
		} catch (IOException e) {
			e.printStackTrace(); // ignore this exception
		}
	}

	private void processException(Exception e) {
		e.printStackTrace();
		shutdown();
	}
	private void processSocketClosed(SocketException e) {
		// this is a normal case, ignore it
		// System.err.println("lsock should be closed: " + e);
	}

	class ReadLSockThread implements Runnable {
		public void run() {
			try {
				bareRun();
			} catch (IOException e) {
				processException(e);
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
			}
		}

		private void bareRun() throws IOException, InterruptedException {
			InputStream in = null;
			try {
				in = lsock.getInputStream();
				byte[] buf = new byte[BUFLEN];
				int len;
				while ((len = in.read(buf)) != -1) {
					byte[] copy = new byte[len];
					System.arraycopy(buf, 0, copy, 0, len);
					lrchannel.put(copy);
					if (dumpRequest)
						System.err.print(new String(copy));
				}
				lrchannel.put(EOF);		// flag the end of lchannel
				in.close();
			} catch (SocketException e) {
				processSocketClosed(e);
			} finally {
				lrchannel.put(EOF);		// flag the end of lchannel
				if (in != null) in.close();
			}
		}
	}

	class WriteRSockThread implements Runnable {
		public void run() {
			try {
				bareRun();
			} catch (IOException e) {
				processException(e);
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
			}
		}

		private void bareRun() throws IOException, InterruptedException {
			OutputStream out = null;
			try {
				out = rsock.getOutputStream();
				while (true) {
					byte[] buf = lrchannel.take();
					if (buf == EOF) break;
					out.write(buf);
				}
			} catch (SocketException e) {
				processSocketClosed(e);
			} finally {
				if (out != null) out.close();
			}
		}
	}

	class ReadRSockThread implements Runnable {
		public void run() {
			try {
				bareRun();
			} catch (IOException e) {
				processException(e);
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
			}
		}

		private void bareRun() throws IOException, InterruptedException {
			InputStream in = null;
			try {
				in = rsock.getInputStream();
				byte[] buf = new byte[BUFLEN];
				int len;
				while ((len = in.read(buf)) != -1) {
					byte[] copy = new byte[len];
					System.arraycopy(buf, 0, copy, 0, len);
					rlchannel.put(copy);
				}
			} catch (SocketException e) {
				processSocketClosed(e);
			} finally {
				// flag the end of rlchannel
				rlchannel.put(EOF);
				// rsock finished, closed it
				in.close();
				rsock.close();
			}
		}
	}

	class WriteLSockThread implements Runnable {
		public void run() {
			try {
				bareRun();
			} catch (IOException e) {
				processException(e);
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
			}
		}

		private void bareRun() throws IOException, InterruptedException {
			OutputStream out = null;
			try {
				out = lsock.getOutputStream();
				while (true) {
					byte[] buf = rlchannel.take();
					if (buf == EOF) break;
					out.write(buf);
					if (dumpResponse)
						System.err.print(new String(buf));
				}
			} catch (SocketException e) {
				processSocketClosed(e);
			} finally {
				if (out != null) out.close();
				lsock.close();		// write finished, close it.
			}
		}
	}
}

