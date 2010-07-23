from multiprocessing import Pool, Lock, Value
from random import random
from time import *

global lock, count, res

def worker(bagsize):
   #Generate bagsize points, and determine 
   #if they are within the circle area
   sum = reduce(lambda x,y: x+(random()**2+random()**2<1.0),
                range(bagsize))
   sum = (4.0*sum)/bagsize

   #Accessing shared vars, acquire lock
   lock.acquire()
   #Add sum to total result
   count.value += 1
   res.value = (res.value*count.value + sum)/(count.value+1)
   #Done accessing shared vars, release lock
   lock.release()


start = time()
bags = 1024
bagsize = 10000

#Startup values
res = Value('d', 0.0)
count = Value('i', 0)
lock = Lock()

#Generate pool of processes
pool = Pool(processes=4)
for i in range(bags):
   pool.apply_async(worker, [bagsize])
pool.close()
pool.join()

end = time()
print "Result:", res.value
print "Time taken (s):", end-start
