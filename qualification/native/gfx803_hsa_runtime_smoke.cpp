// Source-owned narrow ROCR/HSA smoke: init, GPU agent, signals, queue.
// Does not replace the original rocrtst / KFDTest suites.
#include <hsa/hsa.h>
#include <cstdio>
#include <cstring>
#include <string>
#define HSA_OK(expr) do { hsa_status_t e=(expr); if(e!=HSA_STATUS_SUCCESS){ \
  const char* descr=nullptr;hsa_status_string(e,&descr); \
  std::fprintf(stderr,"HSA_FAIL call=%s code=%d desc=%s\n",#expr,int(e),descr?descr:"");return 3;} \
}while(0)
struct State {hsa_agent_t gpu;int count;};
static hsa_status_t visit(hsa_agent_t agent,void* data){
  hsa_device_type_t kind;
  if(hsa_agent_get_info(agent,HSA_AGENT_INFO_DEVICE,&kind)!=HSA_STATUS_SUCCESS)
    return HSA_STATUS_SUCCESS;
  if(kind==HSA_DEVICE_TYPE_GPU) {State* s=(State*)data;s->gpu=agent;s->count++;}
  return HSA_STATUS_SUCCESS;
}
int main(int argc,char**argv){
  if(argc!=2)return 2;
  std::string mode=argv[1];
  HSA_OK(hsa_init());State state{};HSA_OK(hsa_iterate_agents(visit,&state));
  if(state.count<1){std::fprintf(stderr,"no HSA GPU agents\n");return 4;}
  if(mode=="agent-enumeration"){
    char name[64]={};HSA_OK(hsa_agent_get_info(state.gpu,HSA_AGENT_INFO_NAME,name));
    std::printf("HSA_AGENT name=%s count=%d\n",name,state.count);
  } else if(mode=="signal-wait"){
    hsa_signal_t signal{};HSA_OK(hsa_signal_create(1,0,nullptr,&signal));
    hsa_signal_store_screlease(signal,0);
    hsa_signal_value_t got=hsa_signal_wait_scacquire(signal,HSA_SIGNAL_CONDITION_EQ,0,1000000000,HSA_WAIT_STATE_ACTIVE);
    HSA_OK(hsa_signal_destroy(signal));
    if(got!=0){std::fprintf(stderr,"signal wait value=%lld\n",(long long)got);return 1;}
  } else if(mode=="queue-create-destroy"){
    uint32_t max_queue=0;HSA_OK(hsa_agent_get_info(state.gpu,HSA_AGENT_INFO_QUEUE_MAX_SIZE,&max_queue));
    if(max_queue<64){std::fprintf(stderr,"small queue max=%u\n",max_queue);return 4;}
    hsa_queue_t* queue=nullptr;
    HSA_OK(hsa_queue_create(state.gpu,64,HSA_QUEUE_TYPE_MULTI,nullptr,nullptr,UINT32_MAX,UINT32_MAX,&queue));
    HSA_OK(hsa_queue_destroy(queue));
  } else {std::fprintf(stderr,"unknown HSA case\n");return 2;}
  HSA_OK(hsa_shut_down());
  std::printf("GFX803_ASSAY case=%s result=PASS\n",mode.c_str());
  std::fflush(stdout);
  return 0;
}
