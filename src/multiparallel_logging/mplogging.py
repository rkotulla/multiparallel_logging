#!/usr/bin/env python3

"""

This module contains all routines to configure and start the multi-processing
safe logging. All log output is queued, and handled in sequence by a separate
logging process.

"""

from __future__ import print_function

import sys
import logging

import queue
import threading
import multiprocessing
import traceback
import atexit

from random import choice, random
import time



def log_slave_setup(msg_queue):
    h = QueueHandler(msg_queue) # Just the one handler needed
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.DEBUG) # send all messages, for demo; no other level or filter logic applied.


def log_master_setup():
    root = logging.getLogger()
    # h = logging.handlers.RotatingFileHandler('/tmp/mptest.log', 'a', 300, 10)
    try:
        h = logging.StreamHandler(stream=sys.stdout)
    except TypeError:
        h = logging.StreamHandler(strm=sys.stdout)
    except:
        raise
    f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    root.addHandler(h)






class QueueHandler(logging.Handler):
    """
    This is a logging handler which sends events to a multiprocessing queue.
    
    """

    def __init__(self, queue):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)

        self.queue = queue
        self.msgcount = 0

    def flush(self):
        pass

    def emit(self, record):

        """
        Emit a record.

        Writes the LogRecord to the queue.
        """
        self.msgcount += 1

        try:
            self.queue.put_nowait(record)
        except AssertionError:
            pass
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            sys.stdout.write("OOppsie!\n")
            sys.stdout.flush()
            self.handleError(record)






def log_master(msg_queue, log_filename=None, debug_filename=None, append_log=True, debug=False):
    """

    This is the main process that handles all log output. 

    Each log-entry is received via the queue that's being fed by all
    sub-processes, and then forwarded to other log-handlers.

    """

    import sys
    root = logging.getLogger()
    try:
        h = logging.NullHandler() #StreamHandler(stream=sys.stdout)
        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h.setFormatter(f)
        root.addHandler(h)
    except AttributeError:
        # This happens in older Python versions that don't have a NULLHandler
        pass
    except:
        raise

    root.propagate = False

    enable_debug = False
    debug_logger = root
    # print("SETUP:", debug_filename, log_filename, append_log)

    open_mode = "a" if (append_log) else "w"

    if (debug_filename is not None):
        try:
            debugfile = open(debug_filename, open_mode)
            enable_debug = True
            print(" ".join(sys.argv), file=debugfile)

            # print 'activating debug output'

            debug_logger = logging.getLogger('debug')
            try:
                h = logging.StreamHandler(stream=debugfile)
            except TypeError:
                h = logging.StreamHandler(strm=debugfile)
            except:
                raise
            f = logging.Formatter('%(asctime)s -- %(levelname)-8s [ %(filename)30s : %(lineno)4s - %(funcName)30s() in %(processName)-12s] %(name)30s :: %(message)s')
            h.setFormatter(f)
            debug_logger.addHandler(h)
            debug_logger.propagate=False
        except:
            print("#@#@#@#@#@# Unable to write to debug file: %s" % (debug_filename))
            print("#@#@#@#@#@# Routing all debug output to stderr")
            debug_logger = logging.getLogger('debug')
            try:
                h = logging.StreamHandler(stream=sys.stderr)
            except TypeError:
                h = logging.StreamHandler(strm=sys.stderr)
            except:
                raise
            f = logging.Formatter('%(asctime)s -- %(levelname)-8s [ %(filename)30s : %(lineno)4s - %(funcName)30s() in %(processName)-12s] %(name)30s :: %(message)s')
            h.setFormatter(f)
            debug_logger.addHandler(h)
            debug_logger.propagate=False

            pass

    #
    # Create a handler for all output that also goes into the display
    #
    info = logging.getLogger('info')
    
    # set format for the terminal output
    try:
        h = logging.StreamHandler(stream=sys.stdout)
    except TypeError:
        h = logging.StreamHandler(strm=sys.stdout)
    except:
        raise
    # Add some specials to make sure we are always writing to a clean line
    # f = logging.Formatter('\r\x1b[2K%(name)s: %(message)s')
    f = logging.Formatter('%(name)s: %(message)s')
    h.setFormatter(f)
    info.addHandler(h)
    
    # 
    # Also write all info/warning/error messages to the logfile
    #
    if (log_filename is not None):

        infolog_file = open(log_filename, open_mode)
        try:
            h = logging.StreamHandler(stream=infolog_file)
        except TypeError:
            h = logging.StreamHandler(strm=infolog_file)
        except:
            raise
        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h.setFormatter(f)
        info.addHandler(h)
        info.propagate = False
            
    msg_received = 0
    while True:
        try:
            try:
                record = msg_queue.get(timeout=1.)
            except (KeyboardInterrupt, SystemExit):
                record = None
            except queue.Empty:
                pass
                continue
            except:
                raise

            if (record is None):
                break

            msg_received += 1
            # Add some logic here

            #print "record-level:",record.levelno, record.levelname, msg_received

            if (enable_debug):
                debug_logger.handle(record)

            if (record.levelno >= logging.INFO or debug):
                info.handle(record) # No level or filter logic applied - just do it!

            msg_queue.task_done()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            import sys, traceback
            print('Whoops! Problem:', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    if (enable_debug):
        print("done with logging, closing file", file=debugfile)
        debugfile.close()

    print("queue handler closed")





def podi_log_master_start(debug_filename=None, log_filename=None, append_log=True, debug=False):
    """
    
    This function creates the logging sub-process that handles all log output.

    This function also prepares the necessary information so we can activate the
    multiprocessing-safe logging in all sub-processes

    """

    msg_queue = multiprocessing.JoinableQueue()

    #
    # Rename the thread name to make a more useful stacktrace
    #
    msg_queue._start_thread()
    msg_queue._thread.name = "QueueFeederThread___ParallelLogging"

    listener = multiprocessing.Process(target=log_master,
                                kwargs={"msg_queue": msg_queue,
                                        'debug_filename': debug_filename,
                                        'log_filename': log_filename,
                                        'append_log': append_log,
                                        'debug': debug,
                                        }
                            )
    listener.start()

    worker_setup = {"msg_queue": msg_queue,
                  "configurer": log_slave_setup}
    
    log_master_info = {"msg_queue": msg_queue,
                       "listener": listener
                   }

    # Also start a logger for the main process
    podi_logger_setup(worker_setup)

    # print_stacktrace()

    return log_master_info, worker_setup


def podi_log_master_quit(log_master_info):
    """
    Shutdown the logging process
    """

    # print("Shutting down logging")
    log_master_info['msg_queue'].put(None)
    try:
        # print "joining log listener"
        log_master_info['listener'].join()
        # print "done joining log listener"
    except (KeyboardInterrupt, SystemExit):
        pass

    # print("Closing queue")
    log_master_info['msg_queue'].close()
    # print("Queue closed, joining thread")
    log_master_info['msg_queue'].join_thread()
    # print("Thread shutdown, all done")

    return


def podi_logger_setup(setup):
    """
    This function re-directs all logging output to the logging queue that feeds
    the logging subprocess.
    """

    if (setup is None):
        return
        # handler = logging.StreamHandler(sys.stdout)
    else:
        handler = QueueHandler(setup['msg_queue'])

    # import sys
    # handler = logging.StreamHandler(stream=sys.stdout)
    logger = logging.getLogger()

    for h in logger.handlers:
        logger.removeHandler(h)

    logger.setLevel(logging.DEBUG)

    f = logging.Formatter('MYLOGGER = %(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
    handler.setFormatter(f)

    logger.addHandler(handler)
    logger.propagate = True

    logger.debug("Started logging for process %s" % (multiprocessing.current_process().name))

    return


def log_exception(name=None):

    etype, error, stackpos = sys.exc_info()

    exception_string = ["\n",
                        "=========== EXCEPTION ==============",
                        "etype: %s" % (str(etype)),
                        "error: %s" % (str(error)),
                        "stackpos: %s" % (str(stackpos)),
                        "---\n",
                        traceback.format_exc(),
                        "--- end\n"
    ]
    logger = logging.getLogger(name)
    logger.critical("\n".join(exception_string))
    return


def log_platform_debug_data():
    logger = logging.getLogger("PLATFORM")
    try:
        import platform
        logger.debug("Python version: %s" % (str(platform.python_version())))
        logger.debug("Python compiler: %s" % (str(platform.python_compiler())))
        logger.debug("Python build: %s" % (str(platform.python_build())))

        logger.debug("OS version: %s" % (str(platform.platform())))

        logger.debug("OS uname: %s" % (" ".join(platform.uname())))
        logger.debug("OS system: %s" % (str(platform.system())))
        logger.debug("OS node: %s" % (str(platform.node())))
        logger.debug("OS release: %s" % (str(platform.release())))
        logger.debug("OS version: %s" % (str(platform.version())))
        logger.debug("OS machine: %s" % (str(platform.machine())))
        logger.debug("OS processor: %s" % (str(platform.processor())))

        logger.debug("interpreter: %s" % (" ".join(platform.architecture())))
    except:
        logger.debug("OS info not available, missing package platform")
        pass

    try:
        import socket
        logger.debug("Socket hostname: %s" % (socket.gethostname()))
    except:
        logger.debug("socket info not available, missing package socket")
        pass

    try:
        import getpass
        logger.debug("username: %s" % (getpass.getuser()))
    except:
        logger.debug("username not available, missing package getpass")
        pass
        
    return


def setup_logging(debug_filename=None, log_filename=None, debug=False, append_log=True):

    # if (options is None):
    #     options = {}

    # Setup everything we need for logging
    log_master_info, log_setup = podi_log_master_start(
        debug_filename=debug_filename,
        log_filename=log_filename,
        debug=debug,
        append_log=append_log
    )
    # options['log_setup'] = log_setup
    # options['log_master_info'] = log_master_info

    log_platform_debug_data()

    # print("Registering atexit function")
    atexit.register(podi_log_master_quit, log_master_info)

    return
    
def shutdown_logging(options):
    podi_log_master_quit(options['log_master_info'])
    return


class fakefile (object):
    def __init__(self):
        self.text = ""
    def write(self, t):
        self.text += t
    def get(self):
        return self.text

def print_stacktrace(sleep=0, logger=None, info=True, stdout=False):

    time.sleep(sleep)

    ff = fakefile()
    print("========================================================", file=ff)
    print("==   STACK TRACE -- BEGIN                             ==", file=ff)
    print("========================================================", file=ff)

    print("\nCurrently running threads:\n -- %s" % ("\n -- ".join([str(x) for x in threading.enumerate()])), file=ff)

    for thread_id, frame in sys._current_frames().items():
        name = thread_id
        #print name, frame

        for thread in threading.enumerate():
            if thread.ident == thread_id:
                name = thread.name
        print("\nSTACK-TRACE for %s" % (name), file=ff)
        traceback.print_stack(frame, file=ff)

    try:
        import psutil
        print("\nList of subprocess of current process:", file=ff)
        this_process = psutil.Process()
        kids = this_process.children(recursive=True)
        if (len(kids) <= 0):
            print("  This process does not have any child-processes", file=ff)
        else:
            now_time = time.time()
            print(" -- %s" % ("\n -- ".join(["ProcID: %5d - %8.3f seconds" % (
                p.pid, now_time-p.create_time()) for p in kids])), file=ff)
    except:

        print("\nList of subprocesses not available, needs psutil package!", file=ff)
        pass

    print("", file=ff)
    print("========================================================", file=ff)
    print("==   STACK TRACE -- END                               ==", file=ff)
    print("========================================================", file=ff)

    if (stdout):
        print(ff.get())
    else:
        if (logger is None):
            logger = logging.getLogger("StackTrace")
        if (info):
            logger.info("\n%s" % (ff.get()))
        else:
            logger.debug("\n%s" % (ff.get()))

    time.sleep(sleep)
    
    return ff.get()


if __name__ == "__main__":

    options = {}
    # log_master_info, log_setup = podi_log_master_start(options)

    # Setup the multi-processing-safe logging
    # podi_logger_setup(options['log_setup'])

    setup_logging(debug_filename="mp.debug", log_filename='mp.log')

    workers = []
    # for i in range(10):
    #     worker = multiprocessing.Process(target=worker_process, kwargs=worker_log)
    #     workers.append(worker)
    #     worker.start()
    # for w in workers:
    #     w.join()

    # print(log_setup)

    for i in range(3):
        worker = multiprocessing.Process(target=test_worker_process)
            # ,
            #                              kwargs={"log_setup": log_setup})
#                                         args=(worker_log))
        workers.append(worker)
        worker.start()
    for w in workers:
        w.join()

    logger = logging.getLogger("main process")

    logger.info('test info')
    logger.debug('test debug')
    logger.critical('test critical')
    logger.error('test error')

    # shutdown_logging(options)

    print("end of program")
    # podi_log_master_quit(log_master_info)
    #    queue.put_nowait(None)
    #    listener.join()
