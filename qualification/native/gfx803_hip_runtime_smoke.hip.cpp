// Source-owned narrow smoke: HIP runtime memory/copy/streams/events/kernel.
// Does NOT replace original HIP/TheRock upstream tests.
#include <hip/hip_runtime.h>
#include <cstdio>
#include <cstring>
#include <vector>
#include <string>
#include <cstdlib>

#define HIP_OK(expr) do { hipError_t e=(expr); if (e!=hipSuccess) { \
  std::fprintf(stderr, "HIP_FAIL call=%s code=%d desc=%s\n", #expr, int(e),hipGetErrorString(e)); \
  return 3; }} while (0)
__global__ void add_seven(int* p,int n) { int i=blockIdx.x*blockDim.x+threadIdx.x; if(i<n) p[i]+=7; }
int main(int argc,char**argv) {
 if(argc!=2){std::fprintf(stderr,"one case name required\n");return 2;}
 std::string mode=argv[1];
 constexpr int N=8192; constexpr size_t BYTES=N*sizeof(int);
 std::vector<int> host(N),result(N);for(int i=0;i<N;i++)host[i]=i%117;
 int *device=nullptr; hipStream_t stream=nullptr;hipEvent_t event=nullptr;
 HIP_OK(hipSetDevice(0));
 HIP_OK(hipMalloc((void**)&device,BYTES));
 if(mode=="h2d-d2h"){
   HIP_OK(hipMemcpy(device,host.data(),BYTES,hipMemcpyHostToDevice));
   HIP_OK(hipMemcpy(result.data(),device,BYTES,hipMemcpyDeviceToHost));
 } else if(mode=="stream-event-copy"){
   HIP_OK(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
   HIP_OK(hipEventCreateWithFlags(&event,hipEventDisableTiming));
   HIP_OK(hipMemcpyAsync(device,host.data(),BYTES,hipMemcpyHostToDevice,stream));
   HIP_OK(hipMemcpyAsync(result.data(),device,BYTES,hipMemcpyDeviceToHost,stream));
   HIP_OK(hipEventRecord(event,stream));HIP_OK(hipEventSynchronize(event));
 } else if(mode=="kernel-dispatch"){
   HIP_OK(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
   HIP_OK(hipMemcpyAsync(device,host.data(),BYTES,hipMemcpyHostToDevice,stream));
   hipLaunchKernelGGL(add_seven,dim3((N+255)/256),dim3(256),0,stream,device,N);
   HIP_OK(hipGetLastError());
   HIP_OK(hipMemcpyAsync(result.data(),device,BYTES,hipMemcpyDeviceToHost,stream));
   HIP_OK(hipStreamSynchronize(stream));
 } else if(mode=="pinned-host-copy"){
   int* pinned=nullptr;
   HIP_OK(hipHostMalloc((void**)&pinned,BYTES,hipHostMallocDefault));
   std::memcpy(pinned,host.data(),BYTES);
   HIP_OK(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
   HIP_OK(hipMemcpyAsync(device,pinned,BYTES,hipMemcpyHostToDevice,stream));
   HIP_OK(hipMemcpyAsync(result.data(),device,BYTES,hipMemcpyDeviceToHost,stream));
   HIP_OK(hipStreamSynchronize(stream));
   HIP_OK(hipHostFree(pinned));
 } else {std::fprintf(stderr,"unknown case\n");return 2;}
 int wrong=0;for(int i=0;i<N;i++)if(result[i]!=host[i]+(mode=="kernel-dispatch"?7:0))wrong++;
 if(event)HIP_OK(hipEventDestroy(event));
 if(stream)HIP_OK(hipStreamDestroy(stream));
 HIP_OK(hipFree(device));
 std::printf("GFX803_ASSAY case=%s count=%d wrong=%d result=%s\n",
             mode.c_str(),N,wrong,wrong?"FAIL":"PASS");
 std::fflush(stdout);
 return wrong?1:0;
}
